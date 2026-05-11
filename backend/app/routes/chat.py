from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import ValidationError

from app.models.chat import ChatRequest, ChatResponse
from app.services.ai_service import AIService, AIServiceError
from app.services.chat_service import ChatService, ConversationNotFoundError
from app.services.file_service import FileService
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


router = APIRouter()
chat_service = ChatService(AIService(), FileService(), SupabaseMemoryService())


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request) -> ChatResponse:
    chat_request, file = await _parse_chat_request(request)
    message = chat_request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        result = await chat_service.send_message(
            message=message,
            conversation_id=chat_request.conversation_id,
            file=file,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Conversation not found.") from error
    except AIServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error
    except MemoryServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error

    return ChatResponse(
        conversation_id=result["conversation_id"],
        response=result["response"],
        messages=result["messages"],
    )


async def _parse_chat_request(request: Request) -> tuple[ChatRequest, Optional[UploadFile]]:
    content_type = request.headers.get("content-type", "")
    file: Optional[UploadFile] = None

    try:
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            message = str(form.get("message") or "")
            conversation_id_value = form.get("conversation_id")
            conversation_id = (
                str(conversation_id_value) if conversation_id_value else None
            )
            file_value = form.get("file")
            if hasattr(file_value, "filename") and hasattr(file_value, "read"):
                file = file_value

            return (
                ChatRequest(
                    message=message,
                    conversation_id=conversation_id,
                    file=file.filename if file else None,
                ),
                file,
            )

        if content_type.startswith("application/json"):
            payload = await request.json()
            return ChatRequest(**payload), None
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON body.") from error

    raise HTTPException(
        status_code=415,
        detail="Use application/json or multipart/form-data.",
    )
