from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.chat import ChatRequest, ChatResponse
from app.services.ai_service import AIService, AIServiceError
from app.services.chat_service import ChatService, ConversationNotFoundError
from app.services.file_service import FileService


router = APIRouter()
chat_service = ChatService(AIService(), FileService())


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    conversation_id: Optional[int] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> ChatResponse:
    request = ChatRequest(
        message=message,
        conversation_id=conversation_id,
        file=file.filename if file else None,
    )
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        result = await chat_service.send_message(
            message=message,
            conversation_id=request.conversation_id,
            file=file,
        )
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Conversation not found.") from error
    except AIServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error

    return ChatResponse(
        conversation_id=result["conversation_id"],
        response=result["response"],
        messages=result["messages"],
    )
