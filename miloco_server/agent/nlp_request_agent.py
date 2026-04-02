# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Chat Agent"""
import asyncio
import json
import logging

from miloco_server.schema.chat_schema import Event, Internal, Nlp
from miloco_server.utils.chat_companion import ChatCachedData
from miloco_server.agent.chat_agent import ChatAgent

logger = logging.getLogger(__name__)

class NlpRequestAgent(ChatAgent):
    """Nlp Request Agent"""

    def _parse_and_handle_event(self, event: Event) -> None:
        """Parse and handle event."""
        if event.judge_type("Nlp", "Request"):
            payload = Nlp.Request(**json.loads(event.payload))
            self._handle_nlp_request(payload)
        else:
            raise ValueError(f"Unsupported event: {event.header.namespace}.{event.header.name}")


    def _handle_nlp_request(self, payload: Nlp.Request) -> None:
        """Handle Nlp request."""
        query = payload.query
        self._send_instruction(Internal.Dispatcher(current_query=query, need_storage_history=True))
        mcp_list = payload.mcp_list
        self._set_tools_meta(mcp_list)

        if payload.camera_ids:
            self._chat_history_messages.add_content(
                "system",
                "The user has already selected camera feeds for this request. "
                "When answering scene, object, person, action, or visual status questions, "
                "you must inspect the selected cameras through available vision tools before answering. "
                "Do not say that you cannot access or view the user's camera when vision tools are available."
            )

        self._chat_companion.set_chat_data(
            self._request_id,
            ChatCachedData(
                camera_ids=payload.camera_ids,
                mcp_ids=payload.mcp_list,
                function_calling_format=payload.function_calling_format,
            ))

        asyncio.create_task(self._run_chat(query))

