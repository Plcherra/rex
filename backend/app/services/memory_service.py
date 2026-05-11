import json
import re
from typing import Optional
from urllib.parse import quote, urlencode

import httpx

from app.config import Settings, get_settings
from app.services.http_client import request_with_retries


class MemoryServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class SupabaseMemoryService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def create_conversation(self) -> str:
        row = await self.create_conversation_record()
        conversation_id = row.get("id")
        if not conversation_id:
            raise MemoryServiceError("Supabase did not return a conversation id.")

        return str(conversation_id)

    async def create_conversation_record(self) -> dict:
        rows = await self._request(
            "POST",
            self.settings.supabase_conversations_table,
            body={},
            query={"select": "id,title,timestamp"},
            prefer="return=representation",
        )
        return self._conversation_with_preview(self._first_row(rows), None)

    async def list_conversations(self, limit: int = 50) -> list[dict]:
        rows = await self._request(
            "GET",
            self.settings.supabase_conversations_table,
            query={
                "select": "id,title,timestamp",
                "order": "timestamp.desc",
                "limit": str(limit),
            },
        )

        conversations = []
        for row in rows:
            conversation_id = str(row.get("id", ""))
            recent_messages = await self.get_recent_messages(conversation_id, limit=1)
            last_message = recent_messages[-1] if recent_messages else None
            conversations.append(self._conversation_with_preview(row, last_message))

        return conversations

    async def conversation_exists(self, conversation_id: str) -> bool:
        rows = await self._request(
            "GET",
            self.settings.supabase_conversations_table,
            query={
                "id": f"eq.{conversation_id}",
                "select": "id",
                "limit": "1",
            },
        )
        return bool(rows)

    async def save_message(self, conversation_id: str, role: str, content: str) -> dict:
        rows = await self._request(
            "POST",
            self.settings.supabase_messages_table,
            body={
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            },
            query={"select": "id,conversation_id,role,content,timestamp"},
            prefer="return=representation",
        )
        return self._first_row(rows)

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[dict]:
        rows = await self._request(
            "GET",
            self.settings.supabase_messages_table,
            query={
                "conversation_id": f"eq.{conversation_id}",
                "select": "id,conversation_id,role,content,timestamp",
                "order": "timestamp.desc",
                "limit": str(limit),
            },
        )
        return list(reversed(rows))

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> Optional[list[dict]]:
        if not await self.conversation_exists(conversation_id):
            return None

        return await self.get_recent_messages(conversation_id, limit=limit)

    async def delete_conversation(self, conversation_id: str) -> bool:
        if not await self.conversation_exists(conversation_id):
            return False

        await self._request(
            "DELETE",
            self.settings.supabase_conversations_table,
            query={"id": f"eq.{conversation_id}"},
        )
        return True

    async def save_long_term_memory(
        self,
        memory_type: str,
        content: str,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        importance: int = 3,
    ) -> dict:
        rows = await self._request(
            "POST",
            self.settings.supabase_long_term_memory_table,
            body={
                "memory_type": memory_type,
                "content": content,
                "source_conversation_id": source_conversation_id,
                "source_message_id": source_message_id,
                "importance": importance,
            },
            query={
                "select": (
                    "id,memory_type,content,source_conversation_id,"
                    "source_message_id,importance,active,created_at,"
                    "updated_at,last_accessed_at"
                )
            },
            prefer="return=representation",
        )
        return self._first_row(rows)

    async def save_long_term_memory_from_message(
        self,
        conversation_id: str,
        message: dict,
    ) -> Optional[dict]:
        memory = self._memory_candidate(str(message.get("content", "")))
        if not memory:
            return None

        return await self.save_long_term_memory(
            memory_type=memory["memory_type"],
            content=memory["content"],
            source_conversation_id=conversation_id,
            source_message_id=str(message.get("id")) if message.get("id") else None,
            importance=memory["importance"],
        )

    async def get_long_term_memory(self, limit: int = 20) -> list[dict]:
        return await self._request(
            "GET",
            self.settings.supabase_long_term_memory_table,
            query={
                "active": "eq.true",
                "select": (
                    "id,memory_type,content,source_conversation_id,"
                    "source_message_id,importance,created_at,last_accessed_at"
                ),
                "order": "importance.desc,last_accessed_at.desc,created_at.desc",
                "limit": str(limit),
            },
        )

    async def _request(
        self,
        method: str,
        table: str,
        body: Optional[dict] = None,
        query: Optional[dict[str, str]] = None,
        prefer: Optional[str] = None,
    ) -> list[dict]:
        rest_url = self.settings.supabase_rest_url
        service_key = self.settings.supabase_service_role_key
        if not rest_url or not service_key:
            raise MemoryServiceError("Supabase memory is not configured.")

        url = f"{rest_url}/{quote(table)}"
        if query:
            url = f"{url}?{urlencode(query)}"

        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
        }
        json_body = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            json_body = body
        if prefer:
            headers["Prefer"] = prefer

        try:
            response = await request_with_retries(
                method,
                url,
                headers=headers,
                json=json_body,
            )
            response.raise_for_status()
            raw_response = response.text
        except httpx.HTTPStatusError as error:
            raise MemoryServiceError("Supabase memory returned an error.") from error
        except (httpx.RequestError, TimeoutError) as error:
            raise MemoryServiceError("Cannot reach Supabase memory.") from error

        if not raw_response:
            return []

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise MemoryServiceError(
                "Supabase memory returned an unreadable response.",
                status_code=500,
            ) from error

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]

        raise MemoryServiceError("Supabase memory returned an unreadable response.")

    def _first_row(self, rows: list[dict]) -> dict:
        if not rows:
            raise MemoryServiceError("Supabase memory returned no rows.")

        return rows[0]

    def _conversation_with_preview(
        self,
        row: dict,
        last_message: Optional[dict],
    ) -> dict:
        return {
            "id": str(row.get("id", "")),
            "title": row.get("title"),
            "timestamp": row.get("timestamp"),
            "last_message": last_message,
        }

    def _memory_candidate(self, message: str) -> Optional[dict]:
        text = " ".join(message.strip().split())
        if not text:
            return None

        lowered = text.lower()
        if lowered.startswith(("remember that ", "remember: ")):
            content = re.sub(r"^remember(?: that|:)\s+", "", text, flags=re.I)
            return {
                "memory_type": self._classify_memory(content),
                "content": content,
                "importance": 5,
            }

        if re.match(r"^i (prefer|like|love|hate|dislike|want|need)\b", lowered):
            return {
                "memory_type": "preference",
                "content": text,
                "importance": 4,
            }

        if re.match(r"^i (am|work|live|have|own|use)\b", lowered):
            return {
                "memory_type": "fact",
                "content": text,
                "importance": 3,
            }

        event_markers = (
            "my birthday is",
            "my anniversary is",
            "i started",
            "i moved",
            "i graduated",
            "i got married",
        )
        if any(marker in lowered for marker in event_markers):
            return {
                "memory_type": "event",
                "content": text,
                "importance": 4,
            }

        return None

    def _classify_memory(self, content: str) -> str:
        lowered = content.lower()
        if any(word in lowered for word in ("prefer", "like", "love", "hate", "want")):
            return "preference"
        if any(word in lowered for word in ("birthday", "anniversary", "started")):
            return "event"

        return "fact"
