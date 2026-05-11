from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    file: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    messages: list[dict]
