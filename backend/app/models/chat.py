from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: Optional[int] = None
    file: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: int
    response: str
    messages: list[dict]
