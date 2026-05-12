from collections.abc import AsyncIterator
from typing import Optional, Protocol

from fastapi import UploadFile

from app.services.ai_service import AIService
from app.services.file_service import FileService
from app.services.memory_extraction_service import MemoryExtractionService
from app.services.prompt_service import PromptService
from app.services.time_context_service import TimeContextService


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

    async def save_long_term_memory(
        self,
        memory_type: str,
        content: str,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        importance: int = 3,
    ) -> dict:
        pass

    async def get_relevant_memories(self, query: str, limit: int = 8) -> list[dict]:
        pass


class ChatService:
    def __init__(
        self,
        ai_service: AIService,
        file_service: FileService,
        memory_service: MemoryService,
        memory_extraction_service: Optional[MemoryExtractionService] = None,
        prompt_service: Optional[PromptService] = None,
        time_context_service: Optional[TimeContextService] = None,
    ) -> None:
        self.ai_service = ai_service
        self.file_service = file_service
        self.memory_service = memory_service
        self.memory_extraction_service = memory_extraction_service
        self.prompt_service = prompt_service or PromptService()
        self.time_context_service = time_context_service or TimeContextService()

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
        long_term_memory = await self.memory_service.get_relevant_memories(
            query=message,
            limit=8,
        )

        if conversation_id is None:
            conversation_id = await self.memory_service.create_conversation()

        ai_messages = self._build_prompt_messages(
            message=message,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            long_term_memory=long_term_memory,
            file_text=file_text,
        )

        user_message = await self.memory_service.save_message(
            conversation_id,
            "user",
            message,
        )

        rex_response = await self.ai_service.generate_response(ai_messages)
        assistant_message = await self.memory_service.save_message(
            conversation_id,
            "assistant",
            rex_response,
        )

        await self._extract_memory_after_success(
            conversation_id,
            user_message,
            assistant_message,
        )

        return {
            "conversation_id": conversation_id,
            "response": rex_response,
            "messages": await self.memory_service.get_recent_messages(
                conversation_id,
                limit=20,
            ),
        }

    async def stream_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file: Optional[UploadFile] = None,
    ) -> AsyncIterator[dict]:
        conversation_id = await self._existing_conversation_id(conversation_id)
        file_text = await self.file_service.read_text_file(file) if file else None

        conversation_history = []
        if conversation_id is not None:
            conversation_history = await self.memory_service.get_recent_messages(
                conversation_id,
                limit=20,
            )
        long_term_memory = await self.memory_service.get_relevant_memories(
            query=message,
            limit=8,
        )

        if conversation_id is None:
            conversation_id = await self.memory_service.create_conversation()

        ai_messages = self._build_prompt_messages(
            message=message,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            long_term_memory=long_term_memory,
            file_text=file_text,
        )

        user_message = await self.memory_service.save_message(
            conversation_id,
            "user",
            message,
        )
        yield {"event": "conversation", "conversation_id": conversation_id}

        response_parts = []
        async for token in self.ai_service.stream_response(ai_messages):
            response_parts.append(token)
            yield {"event": "token", "token": token}

        rex_response = "".join(response_parts).strip()
        assistant_message = await self.memory_service.save_message(
            conversation_id,
            "assistant",
            rex_response,
        )

        await self._extract_memory_after_success(
            conversation_id,
            user_message,
            assistant_message,
        )

        yield {
            "event": "done",
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

    def _build_prompt_messages(
        self,
        message: str,
        conversation_id: str,
        conversation_history: list[dict],
        long_term_memory: list[dict],
        file_text: Optional[str],
    ) -> list[dict]:
        last_message_timestamp = self._last_message_timestamp(conversation_history)
        return self.prompt_service.build_messages(
            user_message=message,
            recent_messages=conversation_history,
            relevant_memories=long_term_memory,
            file_context=file_text,
            conversation_metadata={
                "id": conversation_id,
                "timestamp": self._conversation_timestamp(conversation_history),
                "last_message_timestamp": last_message_timestamp,
            },
            time_context=self.time_context_service.current_context(
                previous_timestamp=last_message_timestamp,
            ),
        )

    def _last_message_timestamp(self, conversation_history: list[dict]) -> Optional[str]:
        if not conversation_history:
            return None
        timestamp = conversation_history[-1].get("timestamp")
        return str(timestamp) if timestamp else None

    def _conversation_timestamp(self, conversation_history: list[dict]) -> Optional[str]:
        if not conversation_history:
            return None
        timestamp = conversation_history[0].get("timestamp")
        return str(timestamp) if timestamp else None

    async def _extract_memory_after_success(
        self,
        conversation_id: str,
        user_message: dict,
        assistant_message: dict,
    ) -> None:
        if self.memory_extraction_service is None:
            return

        try:
            await self.memory_extraction_service.extract_and_save(
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_message=assistant_message,
            )
        except Exception:
            # Memory extraction is best-effort. A failed extraction must not
            # break a successful chat response.
            return
