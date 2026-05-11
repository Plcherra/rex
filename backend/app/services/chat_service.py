from typing import Optional, Protocol

from fastapi import UploadFile

from app.services.ai_service import AIService
from app.services.file_service import FileService

MAX_CONTEXT_CHARACTERS = 24000
FILE_CONTEXT_PREFIX = "Uploaded file content:\n\n"
LONG_TERM_MEMORY_PREFIX = "Relevant long-term memory:\n"


class ConversationNotFoundError(Exception):
    pass


class MemoryService(Protocol):
    async def create_conversation(self) -> str:
        pass

    async def conversation_exists(self, conversation_id: str) -> bool:
        pass

    async def save_message(self, conversation_id: str, role: str, content: str) -> dict:
        pass

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[dict]:
        pass

    async def save_long_term_memory_from_message(
        self,
        conversation_id: str,
        message: dict,
    ) -> Optional[dict]:
        pass

    async def get_long_term_memory(self, limit: int = 20) -> list[dict]:
        pass


class ChatService:
    def __init__(
        self,
        ai_service: AIService,
        file_service: FileService,
        memory_service: MemoryService,
    ) -> None:
        self.ai_service = ai_service
        self.file_service = file_service
        self.memory_service = memory_service

    async def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file: Optional[UploadFile] = None,
    ) -> dict:
        conversation_id = await self._existing_conversation_id(conversation_id)
        file_text = await self.file_service.read_text_file(file) if file else None

        conversation_history = []
        if conversation_id is not None:
            conversation_history = await self.memory_service.get_recent_messages(
                conversation_id,
                limit=20,
            )
        long_term_memory = await self.memory_service.get_long_term_memory(limit=20)

        ai_messages = [
            *conversation_history,
            {"role": "user", "content": message},
        ]
        ai_messages = self._messages_with_file_context(ai_messages, file_text)
        ai_messages = self._messages_with_long_term_memory(
            ai_messages,
            long_term_memory,
        )
        ai_messages = self._trim_context(ai_messages)

        rex_response = await self.ai_service.generate_response(ai_messages)
        if conversation_id is None:
            conversation_id = await self.memory_service.create_conversation()

        user_message = await self.memory_service.save_message(
            conversation_id,
            "user",
            message,
        )
        await self.memory_service.save_long_term_memory_from_message(
            conversation_id,
            user_message,
        )
        await self.memory_service.save_message(
            conversation_id,
            "assistant",
            rex_response,
        )

        return {
            "conversation_id": conversation_id,
            "response": rex_response,
            "messages": await self.memory_service.get_recent_messages(
                conversation_id,
                limit=20,
            ),
        }

    async def _existing_conversation_id(
        self,
        conversation_id: Optional[str],
    ) -> Optional[str]:
        if conversation_id is None:
            return None

        if not await self.memory_service.conversation_exists(conversation_id):
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

    def _messages_with_long_term_memory(
        self,
        messages: list[dict],
        long_term_memory: list[dict],
    ) -> list[dict]:
        if not long_term_memory:
            return messages

        memory_lines = [
            f"- {memory['memory_type']}: {memory['content']}"
            for memory in long_term_memory
            if memory.get("memory_type") and memory.get("content")
        ]
        if not memory_lines:
            return messages

        return [
            {
                "role": "system",
                "content": f"{LONG_TERM_MEMORY_PREFIX}{chr(10).join(memory_lines)}",
            },
            *messages,
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
