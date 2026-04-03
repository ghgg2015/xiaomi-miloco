# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Vision model adapter abstractions and factory."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from miloco_server.schema.auth_schema import UserLanguage
from miloco_server.schema.miot_schema import CameraImgSeq
from miloco_server.schema.model_schema import ThirdPartyModelInfo
from miloco_server.utils.prompt_helper import VisionUnderstandToolPromptBuilder
from miloco_server.utils.local_models import ModelPurpose

logger = logging.getLogger(__name__)


class VisionAdapterType(str, Enum):
    """Supported vision adapter types."""

    OPENAI_COMPATIBLE = "openai_compatible"
    QWEN_COMPATIBLE = "qwen_compatible"


@dataclass
class VisionAnalyzeResult:
    """Normalized vision analysis result."""

    content: Optional[str]
    raw_response: Optional[object] = None
    adapter_type: Optional[str] = None


class VisionModelAdapter(ABC):
    """Abstract vision model adapter."""

    def __init__(self, request_id: str):
        self._request_id = request_id

    @abstractmethod
    async def analyze_images(
        self,
        query: str,
        camera_img_seqs: list[CameraImgSeq],
        language: UserLanguage,
    ) -> VisionAnalyzeResult:
        """Analyze image sequences and return normalized result."""

    @staticmethod
    def sanitize_output(content: Optional[str]) -> Optional[str]:
        """Remove reasoning wrappers and keep user-facing content only."""
        if not content:
            return content

        final_answer_match = re.search(
            r"<final_answer>\s*(.*?)\s*</final_answer>",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if final_answer_match:
            return final_answer_match.group(1).strip()

        cleaned = re.sub(
            r"<reflect>.*?</reflect>",
            "",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        cleaned = re.sub(
            r"<think>.*?</think>",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        return cleaned or content.strip()


class OpenAICompatibleVisionAdapter(VisionModelAdapter):
    """Adapter for OpenAI-compatible multimodal chat APIs."""

    def __init__(self, request_id: str, llm_proxy):
        super().__init__(request_id=request_id)
        self._llm_proxy = llm_proxy

    async def analyze_images(
        self,
        query: str,
        camera_img_seqs: list[CameraImgSeq],
        language: UserLanguage,
    ) -> VisionAnalyzeResult:
        chat_history = VisionUnderstandToolPromptBuilder.build_prompt(
            camera_img_seqs=camera_img_seqs,
            query=query,
            language=language,
        )

        llm_result = await self._llm_proxy.async_call_llm(
            chat_history.get_messages(),
            tools=None,
        )
        logger.info("[%s] Vision adapter raw response: %s", self._request_id, llm_result)

        if not llm_result.get("success", False):
            error = llm_result.get("error", "Unknown error")
            raise RuntimeError(f"Vision model call failed: {error}")

        response = llm_result["response"]
        choices = response.choices
        if not choices:
            raise RuntimeError("No choices in vision model response")

        content = choices[0].message.content
        return VisionAnalyzeResult(
            content=self.sanitize_output(content),
            raw_response=response,
            adapter_type=VisionAdapterType.OPENAI_COMPATIBLE.value,
        )


class QwenCompatibleVisionAdapter(OpenAICompatibleVisionAdapter):
    """Adapter for Qwen-compatible multimodal APIs."""

    async def analyze_images(
        self,
        query: str,
        camera_img_seqs: list[CameraImgSeq],
        language: UserLanguage,
    ) -> VisionAnalyzeResult:
        result = await super().analyze_images(
            query=query,
            camera_img_seqs=camera_img_seqs,
            language=language,
        )
        result.adapter_type = VisionAdapterType.QWEN_COMPATIBLE.value
        return result


class VisionAdapterFactory:
    """Factory for creating vision adapters."""

    @staticmethod
    def infer_adapter_type(model_info: Optional[ThirdPartyModelInfo]) -> VisionAdapterType:
        """Infer adapter type from model metadata heuristically."""
        if not model_info:
            return VisionAdapterType.OPENAI_COMPATIBLE

        api_style = (getattr(model_info, "api_style", "") or "").lower()
        provider = (getattr(model_info, "provider", "") or "").lower()
        model_name = (model_info.model_name or "").lower()
        base_url = (model_info.base_url or "").lower()
        if api_style == "qwen_xml" or provider == "qwen":
            return VisionAdapterType.QWEN_COMPATIBLE
        if api_style == "openai_compatible":
            return VisionAdapterType.OPENAI_COMPATIBLE
        if "qwen" in model_name or "dashscope" in base_url or "aliyuncs" in base_url:
            return VisionAdapterType.QWEN_COMPATIBLE
        return VisionAdapterType.OPENAI_COMPATIBLE

    @staticmethod
    def create_adapter(request_id: str, model_info: Optional[ThirdPartyModelInfo], llm_proxy) -> VisionModelAdapter:
        """Create adapter instance for the given model."""
        adapter_type = VisionAdapterFactory.infer_adapter_type(model_info)
        logger.info("[%s] Creating vision adapter type=%s for model=%s", request_id, adapter_type, getattr(model_info, "model_name", None))

        if adapter_type == VisionAdapterType.QWEN_COMPATIBLE:
            return QwenCompatibleVisionAdapter(request_id=request_id, llm_proxy=llm_proxy)
        return OpenAICompatibleVisionAdapter(request_id=request_id, llm_proxy=llm_proxy)
