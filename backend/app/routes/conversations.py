from fastapi import APIRouter, Depends, HTTPException, Response

from app.dependencies import get_memory_service
from app.models.conversation import ConversationResponse, MessageResponse
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> list[ConversationResponse]:
    try:
        conversations = await memory_service.list_conversations()
    except MemoryServiceError as error:
        raise _memory_http_error(error) from error

    return [ConversationResponse(**conversation) for conversation in conversations]


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> ConversationResponse:
    try:
        conversation = await memory_service.create_conversation_record()
    except MemoryServiceError as error:
        raise _memory_http_error(error) from error

    return ConversationResponse(**conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> list[MessageResponse]:
    try:
        messages = await memory_service.get_conversation_messages(conversation_id)
    except MemoryServiceError as error:
        raise _memory_http_error(error) from error

    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return [MessageResponse(**message) for message in messages]


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> Response:
    try:
        deleted = await memory_service.delete_conversation(conversation_id)
    except MemoryServiceError as error:
        raise _memory_http_error(error) from error

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return Response(status_code=204)


def _memory_http_error(error: MemoryServiceError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)
