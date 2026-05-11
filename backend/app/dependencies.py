from fastapi import Depends

from app.services.ai_service import AIService
from app.services.chat_service import ChatService
from app.services.file_service import FileService
from app.services.memory_extraction_service import MemoryExtractionService
from app.services.memory_service import SupabaseMemoryService


def get_ai_service() -> AIService:
    return AIService()


def get_memory_service() -> SupabaseMemoryService:
    return SupabaseMemoryService()


def get_chat_service(
    ai_service: AIService = Depends(get_ai_service),
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> ChatService:
    return ChatService(
        ai_service,
        FileService(),
        memory_service,
        MemoryExtractionService(ai_service, memory_service),
    )
