import json
import re
from difflib import SequenceMatcher
from typing import Optional, Protocol

from app.services.ai_service import AIService

VALID_MEMORY_TYPES = {"fact", "preference", "event"}
MIN_IMPORTANCE_TO_SAVE = 3
DUPLICATE_SIMILARITY_THRESHOLD = 0.86
DUPLICATE_TOKEN_OVERLAP_THRESHOLD = 0.72

MEMORY_EXTRACTION_PROMPT = """
You extract durable long-term memory for Rex, a private personal AI assistant.

Return ONLY valid JSON. No markdown. No commentary.

Schema:
{
  "memories": [
    {
      "memory_type": "fact" | "preference" | "event",
      "content": "short first-person memory about the user",
      "importance": 1 | 2 | 3 | 4 | 5,
      "rationale": "why this should be remembered"
    }
  ]
}

Extract zero or more memories from the chat turn.
Save only stable information that will help future advice.
Good memory examples:
- user facts: job, immigration status, living situation, money stress, goals
- preferences: communication style, recurring likes/dislikes, decision criteria
- important events: deadlines, moves, relationship changes, work changes

Do not extract:
- one-off emotions without durable context
- generic requests or instructions to answer the current question
- assistant advice
- duplicates of existing memories
- private sensitive details unless the user clearly stated them as personal context

Use importance:
1-2 = weak/noisy, usually do not save
3 = useful context
4 = important recurring context
5 = critical identity, legal, financial, health, relationship, or life context

If there is nothing worth remembering, return {"memories": []}.
""".strip()


class MemoryStore(Protocol):
    async def get_relevant_memories(self, query: str, limit: int = 8) -> list[dict]:
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


class MemoryExtractionService:
    def __init__(self, ai_service: AIService, memory_service: MemoryStore) -> None:
        self.ai_service = ai_service
        self.memory_service = memory_service

    async def extract_and_save(
        self,
        conversation_id: str,
        user_message: dict,
        assistant_message: dict,
    ) -> list[dict]:
        raw_response = await self.ai_service.generate_response(
            [
                {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
                {
                    "role": "user",
                    "content": self._turn_payload(user_message, assistant_message),
                },
            ]
        )
        candidates = self._parse_candidates(raw_response)
        saved_memories = []

        for candidate in candidates:
            normalized = self._normalize_candidate(candidate)
            if normalized is None:
                continue
            if await self._is_duplicate(normalized["content"]):
                continue

            saved = await self.memory_service.save_long_term_memory(
                memory_type=normalized["memory_type"],
                content=normalized["content"],
                source_conversation_id=conversation_id,
                source_message_id=str(user_message.get("id"))
                if user_message.get("id")
                else None,
                importance=normalized["importance"],
            )
            saved_memories.append(
                {
                    **saved,
                    "extraction_rationale": normalized["rationale"],
                }
            )

        return saved_memories

    def _turn_payload(self, user_message: dict, assistant_message: dict) -> str:
        return json.dumps(
            {
                "user_message": str(user_message.get("content", "")),
                "assistant_response": str(assistant_message.get("content", "")),
            },
            ensure_ascii=True,
        )

    def _parse_candidates(self, raw_response: str) -> list[dict]:
        payload = self._extract_json_payload(raw_response)
        data = json.loads(payload)

        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            candidates = data.get("memories", [])
        else:
            return []

        return [
            candidate
            for candidate in candidates
            if isinstance(candidate, dict)
        ]

    def _extract_json_payload(self, raw_response: str) -> str:
        text = raw_response.strip()
        fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
        if fenced_match:
            return fenced_match.group(1).strip()

        object_start = text.find("{")
        object_end = text.rfind("}")
        list_start = text.find("[")
        list_end = text.rfind("]")

        if list_start != -1 and (
            object_start == -1 or list_start < object_start
        ) and list_end > list_start:
            return text[list_start : list_end + 1]
        if object_start != -1 and object_end > object_start:
            return text[object_start : object_end + 1]
        if list_start != -1 and list_end > list_start:
            return text[list_start : list_end + 1]

        return text

    def _normalize_candidate(self, candidate: dict) -> Optional[dict]:
        memory_type = str(candidate.get("memory_type", "")).strip().lower()
        content = " ".join(str(candidate.get("content", "")).split())
        rationale = " ".join(str(candidate.get("rationale", "")).split())

        try:
            importance = int(candidate.get("importance", 0))
        except (TypeError, ValueError):
            return None

        if memory_type not in VALID_MEMORY_TYPES:
            return None
        if importance < MIN_IMPORTANCE_TO_SAVE or importance > 5:
            return None
        if len(content) < 8 or self._looks_noisy(content):
            return None

        return {
            "memory_type": memory_type,
            "content": content,
            "importance": importance,
            "rationale": rationale or "Useful future context.",
        }

    def _looks_noisy(self, content: str) -> bool:
        lowered = content.lower()
        noisy_phrases = (
            "the user asked",
            "the user wants an answer",
            "assistant should",
            "rex should",
            "current question",
            "this conversation",
        )
        return any(phrase in lowered for phrase in noisy_phrases)

    async def _is_duplicate(self, content: str) -> bool:
        existing_memories = await self.memory_service.get_relevant_memories(
            query=content,
            limit=20,
        )
        normalized_content = self._normalized_text(content)
        content_tokens = set(normalized_content.split())

        for memory in existing_memories:
            existing_content = str(memory.get("content", ""))
            normalized_existing = self._normalized_text(existing_content)
            if not normalized_existing:
                continue
            if normalized_existing == normalized_content:
                return True

            similarity = SequenceMatcher(
                None,
                normalized_content,
                normalized_existing,
            ).ratio()
            existing_tokens = set(normalized_existing.split())
            token_overlap = len(content_tokens & existing_tokens) / max(
                len(content_tokens | existing_tokens),
                1,
            )

            if (
                similarity >= DUPLICATE_SIMILARITY_THRESHOLD
                or token_overlap >= DUPLICATE_TOKEN_OVERLAP_THRESHOLD
            ):
                return True

        return False

    def _normalized_text(self, text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", text.lower()))
