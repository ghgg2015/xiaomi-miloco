# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Vision understanding facade built on top of model adapters."""

import logging

from miloco_server.schema.auth_schema import UserLanguage
from miloco_server.schema.miot_schema import CameraImgSeq
from miloco_server.utils.local_models import ModelPurpose

logger = logging.getLogger(__name__)


class VisionUnderstander:
    """Facade for understanding and processing vision-related tasks."""

    def __init__(
        self,
        request_id: str,
        query: str,
        camera_img_seqs: list[CameraImgSeq],
        language: UserLanguage,
    ):
        """Initialize VisionUnderstander."""
        from miloco_server.service.manager import get_manager  # pylint: disable=import-outside-toplevel

        self._manager = get_manager()
        self._request_id = request_id
        self._query = query
        self._camera_img_seqs = camera_img_seqs
        self._language = language
        self._vision_adapter = self._manager.get_vision_adapter_by_purpose(
            ModelPurpose.VISION_UNDERSTANDING,
            request_id=self._request_id,
        )
        logger.info(
            "[%s] VisionUnderstander initialized, adapter: %s",
            self._request_id,
            self._vision_adapter,
        )

    async def run(self) -> str | None:
        """Run adapter to process vision query."""
        logger.info("[%s] Starting vision understanding", self._request_id)
        if not self._vision_adapter:
            raise RuntimeError(
                "Vision model adapter not exist, Please configure on the Model Settings Page."
            )

        result = await self._vision_adapter.analyze_images(
            query=self._query,
            camera_img_seqs=self._camera_img_seqs,
            language=self._language,
        )
        return result.content
