from fastapi import Depends

from app.services.ai_service import AIService
from app.services.chat_service import ChatService
from app.services.commitment_service import CommitmentService
from app.services.deepgram_service import DeepgramService
from app.services.deepgram_streaming_service import DeepgramStreamingService
from app.services.entity_service import EntityService
from app.services.file_service import FileService
from app.services.google_tts_service import GoogleTTSService
from app.services.memory_extraction_service import MemoryExtractionService
from app.services.memory_service import SupabaseMemoryService
from app.services.plan_service import PlanService
from app.services.rule_service import RuleService


def get_ai_service() -> AIService:
    return AIService()


def get_memory_service() -> SupabaseMemoryService:
    return SupabaseMemoryService()


def get_entity_service(
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> EntityService:
    return EntityService(memory_service)


def get_rule_service(
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> RuleService:
    return RuleService(memory_service)


def get_plan_service(
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> PlanService:
    return PlanService(memory_service)


def get_commitment_service(
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> CommitmentService:
    return CommitmentService(memory_service)


def get_deepgram_service() -> DeepgramService:
    return DeepgramService()


def get_deepgram_streaming_service() -> DeepgramStreamingService:
    return DeepgramStreamingService()


def get_google_tts_service() -> GoogleTTSService:
    return GoogleTTSService()


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
