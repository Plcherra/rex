import asyncio
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

    async def get_structured_memory_context(self, query: str) -> dict:
        pass

    async def save_voice_turn(
        self,
        conversation_id: str,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
        transcript_confidence: Optional[float] = None,
        audio_duration_seconds: Optional[float] = None,
        input_mime_type: Optional[str] = None,
        output_audio_encoding: Optional[str] = None,
        stt_vendor: str = "deepgram",
        tts_vendor: str = "google_tts",
        metadata: Optional[dict] = None,
    ) -> dict:
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
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file: Optional[UploadFile] = None,
    ) -> dict:
        conversation_id = await self._existing_conversation_id(conversation_id)
        file_text = await self.file_service.read_text_file(file) if file else None

        (
            conversation_history,
            long_term_memory,
            structured_context,
        ) = await self._fetch_prompt_context(
            message=message,
            conversation_id=conversation_id,
        )

        if conversation_id is None:
            conversation_id = await self.memory_service.create_conversation()

        ai_messages = self._build_prompt_messages(
            message=message,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            long_term_memory=long_term_memory,
            structured_context=structured_context,
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
            "user_message": user_message,
            "assistant_message": assistant_message,
            "messages": await self.memory_service.get_recent_messages(
                conversation_id,
                limit=20,
            ),
        }

    async def save_voice_turn_metadata(
        self,
        conversation_id: str,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
        transcript_confidence: Optional[float] = None,
        audio_duration_seconds: Optional[float] = None,
        input_mime_type: Optional[str] = None,
        output_audio_encoding: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        try:
            return await self.memory_service.save_voice_turn(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                transcript_confidence=transcript_confidence,
                audio_duration_seconds=audio_duration_seconds,
                input_mime_type=input_mime_type,
                output_audio_encoding=output_audio_encoding,
                metadata=metadata,
            )
        except Exception:
            # Voice metadata is useful for debugging, but raw conversation
            # success should not depend on trace metadata persistence.
            return None

    async def stream_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file: Optional[UploadFile] = None,
    ) -> AsyncIterator[dict]:
        conversation_id = await self._existing_conversation_id(conversation_id)
        file_text = await self.file_service.read_text_file(file) if file else None

        (
            conversation_history,
            long_term_memory,
            structured_context,
        ) = await self._fetch_prompt_context(
            message=message,
            conversation_id=conversation_id,
        )

        if conversation_id is None:
            conversation_id = await self.memory_service.create_conversation()

        ai_messages = self._build_prompt_messages(
            message=message,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            long_term_memory=long_term_memory,
            structured_context=structured_context,
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

        self._schedule_memory_extraction(
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

    async def _fetch_prompt_context(
        self,
        message: str,
        conversation_id: Optional[str],
    ) -> tuple[list[dict], list[dict], dict]:
        long_term_memory_task = self.memory_service.get_relevant_memories(
            query=message,
            limit=8,
        )
        structured_context_task = self._fetch_structured_context(message)
        if conversation_id is None:
            long_term_memory, structured_context = await asyncio.gather(
                long_term_memory_task,
                structured_context_task,
            )
            return [], long_term_memory, structured_context

        return await asyncio.gather(
            self.memory_service.get_recent_messages(conversation_id, limit=20),
            long_term_memory_task,
            structured_context_task,
        )

    async def _fetch_structured_context(self, message: str) -> dict:
        get_structured_context = getattr(
            self.memory_service,
            "get_structured_memory_context",
            None,
        )
        if get_structured_context is None:
            return {}

        try:
            return await get_structured_context(message)
        except Exception:
            return {}

    def _build_prompt_messages(
        self,
        message: str,
        conversation_id: str,
        conversation_history: list[dict],
        long_term_memory: list[dict],
        structured_context: dict,
        file_text: Optional[str],
    ) -> list[dict]:
        last_message_timestamp = self._last_message_timestamp(conversation_history)
        return self.prompt_service.build_messages(
            user_message=message,
            recent_messages=conversation_history,
            relevant_memories=long_term_memory,
            structured_context=structured_context,
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

    def _schedule_memory_extraction(
        self,
        conversation_id: str,
        user_message: dict,
        assistant_message: dict,
    ) -> None:
        if self.memory_extraction_service is None:
            return

        task = asyncio.create_task(
            self._extract_memory_after_success(
                conversation_id,
                user_message,
                assistant_message,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
