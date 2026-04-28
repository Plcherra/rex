from typing import Optional

from fastapi import UploadFile

from app.services.ai_service import AIService
from app.services.file_service import FileService
from app.services.memory_service import (
    conversation_exists,
    create_conversation,
    get_recent_messages,
    save_message,
)


MAX_CONTEXT_CHARACTERS = 24000
FILE_CONTEXT_PREFIX = "Uploaded file content:\n\n"


class ConversationNotFoundError(Exception):
    pass


class ChatService:
    def __init__(
        self,
        ai_service: AIService,
        file_service: FileService,
    ) -> None:
        self.ai_service = ai_service
        self.file_service = file_service

    async def send_message(
        self,
        message: str,
        conversation_id: Optional[int] = None,
        file: Optional[UploadFile] = None,
    ) -> dict:
        conversation_id = self._conversation_id(conversation_id)

        save_message(conversation_id, "user", message)
        conversation_history = get_recent_messages(conversation_id, limit=20)
        file_text = await self.file_service.read_text_file(file) if file else None

        ai_messages = self._messages_with_file_context(conversation_history, file_text)
        ai_messages = self._trim_context(ai_messages)

        rex_response = self.ai_service.generate_response(ai_messages)
        save_message(conversation_id, "assistant", rex_response)

        return {
            "conversation_id": conversation_id,
            "response": rex_response,
            "messages": get_recent_messages(conversation_id, limit=20),
        }

    def _conversation_id(self, conversation_id: Optional[int]) -> int:
        if conversation_id is None:
            return create_conversation()

        if not conversation_exists(conversation_id):
            raise ConversationNotFoundError()

        return conversation_id

    def _messages_with_file_context(
        self,
        messages: list[dict],
        file_text: Optional[str],
    ) -> list[dict]:
        if not file_text:
            return messages

        file_message = {
            "role": "user",
            "content": f"{FILE_CONTEXT_PREFIX}{file_text}",
        }
        if not messages:
            return [file_message]

        return [
            *messages[:-1],
            file_message,
            messages[-1],
        ]

    def _trim_context(self, messages: list[dict]) -> list[dict]:
        trimmed_messages = list(messages)
        while (
            len(trimmed_messages) > 1
            and self._context_length(trimmed_messages) > MAX_CONTEXT_CHARACTERS
        ):
            if len(trimmed_messages) == 2 and self._has_file_context(
                trimmed_messages[0]
            ):
                break

            trimmed_messages = trimmed_messages[1:]

        trimmed_messages = self._trim_file_context(trimmed_messages)
        if self._context_length(trimmed_messages) > MAX_CONTEXT_CHARACTERS:
            last_message = trimmed_messages[-1]
            return [
                {
                    **last_message,
                    "content": last_message["content"][-MAX_CONTEXT_CHARACTERS:],
                }
            ]

        return trimmed_messages

    def _context_length(self, messages: list[dict]) -> int:
        return sum(len(message["content"]) for message in messages)

    def _trim_file_context(self, messages: list[dict]) -> list[dict]:
        if len(messages) < 2 or not self._has_file_context(messages[0]):
            return messages

        latest_message = messages[-1]
        truncation_note = "\n\n[File truncated]"
        available_file_characters = (
            MAX_CONTEXT_CHARACTERS
            - len(latest_message["content"])
            - len(FILE_CONTEXT_PREFIX)
            - len(truncation_note)
        )
        if available_file_characters <= 0:
            return [latest_message]

        file_message = messages[0]
        file_text = file_message["content"][len(FILE_CONTEXT_PREFIX) :]
        if len(file_text) <= available_file_characters:
            return messages

        return [
            {
                **file_message,
                "content": (
                    f"{FILE_CONTEXT_PREFIX}"
                    f"{file_text[:available_file_characters]}{truncation_note}"
                ),
            },
            latest_message,
        ]

    def _has_file_context(self, message: dict) -> bool:
        return message["content"].startswith(FILE_CONTEXT_PREFIX)
