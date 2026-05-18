import json
import re
from difflib import SequenceMatcher
from typing import Any, Optional, Protocol

from app.models.commitment import CommitmentCreateRequest, CommitmentType
from app.models.entity import EntityCreateRequest, EntityEventCreateRequest, EntityType
from app.models.personal_rule import PersonalRuleCreateRequest, RuleType
from app.models.plan import PlanCreateRequest, PlanMilestoneCreateRequest, PlanType
from app.services.ai_service import AIService

VALID_MEMORY_TYPES = {"fact", "preference", "event"}
VALID_STRUCTURED_SECTIONS = {
    "entities",
    "entity_events",
    "personal_rules",
    "plans",
    "plan_milestones",
    "commitments",
}
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
  ],
  "structured_memories": {
    "entities": [
      {
        "entity_type": "person" | "place" | "organization" | "job" | "project" | "object" | "topic" | "other",
        "display_name": "specific name, for example Clara or Bom Dough",
        "normalized_name": "lowercase searchable name",
        "aliases": ["optional alternate names"],
        "relationship": "how this relates to the user, if known",
        "summary": "short durable summary",
        "importance": 1 | 2 | 3 | 4 | 5,
        "rationale": "why this entity matters"
      }
    ],
    "entity_events": [
      {
        "entity_id": "only include if already known",
        "entity_name": "specific entity name if ID is unknown",
        "event_type": "note" | "interaction" | "relationship_update" | "preference" | "commitment" | "conflict" | "milestone" | "other",
        "title": "short event title",
        "content": "what happened",
        "importance": 1 | 2 | 3 | 4 | 5,
        "rationale": "why this event matters"
      }
    ],
    "personal_rules": [
      {
        "rule_type": "finance" | "transport" | "food_delivery" | "coffee" | "rent" | "health" | "dating" | "work" | "immigration" | "personal" | "other",
        "title": "short rule name",
        "rule_text": "the user's rule or boundary",
        "trigger_keywords": ["terms Rex should watch for"],
        "priority": 1 | 2 | 3 | 4 | 5,
        "rationale": "why Rex should enforce this"
      }
    ],
    "plans": [
      {
        "plan_type": "finance" | "immigration" | "career" | "health" | "dating" | "housing" | "creative" | "personal" | "other",
        "title": "short plan name",
        "description": "what the plan is",
        "desired_outcome": "what success looks like",
        "priority": 1 | 2 | 3 | 4 | 5,
        "rationale": "why this plan matters"
      }
    ],
    "plan_milestones": [
      {
        "plan_id": "only include if already known",
        "plan_title": "plan title if ID is unknown",
        "title": "milestone title",
        "description": "what must happen",
        "milestone_type": "goal" | "deadline" | "checkpoint" | "task" | "other",
        "target_date": "ISO date if known",
        "priority": 1 | 2 | 3 | 4 | 5,
        "rationale": "why this milestone matters"
      }
    ],
    "commitments": [
      {
        "commitment_type": "task" | "habit" | "promise" | "money" | "health" | "relationship" | "work" | "immigration" | "deadline" | "other",
        "title": "short commitment name",
        "commitment_text": "what the user committed to",
        "due_at": "ISO timestamp/date if known",
        "priority": 1 | 2 | 3 | 4 | 5,
        "rationale": "why this should be tracked"
      }
    ]
  }
}

Extract zero or more memories from the chat turn.
Save only stable information that will help future advice.
Good memory examples:
- user facts: job, immigration status, living situation, money stress, goals
- preferences: communication style, recurring likes/dislikes, decision criteria
- important events: deadlines, moves, relationship changes, work changes
- named entities: people, jobs, places, products, recurring topics
- personal rules: no Uber, no DoorDash, coffee rules, grocery caps, rent rules
- commitments: "I will work out tomorrow", "I'll apply by Friday"
- multi-step plans: moving countries, income targets, immigration timelines

Do not extract:
- one-off emotions without durable context
- generic requests or instructions to answer the current question
- assistant advice
- duplicates of existing memories
- private sensitive details unless the user clearly stated them as personal context
- vague entities like "someone", "a girl", "work", or "money" unless named or clearly durable

Use importance:
1-2 = weak/noisy, usually do not save
3 = useful context
4 = important recurring context
5 = critical identity, legal, financial, health, relationship, or life context

If there is nothing worth remembering, return {"memories": [], "structured_memories": {}}.
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

    async def create_entity(self, payload: dict) -> dict:
        pass

    async def create_entity_event(self, payload: dict) -> dict:
        pass

    async def create_personal_rule(self, payload: dict) -> dict:
        pass

    async def create_plan(self, payload: dict) -> dict:
        pass

    async def create_plan_milestone(self, payload: dict) -> dict:
        pass

    async def create_commitment(self, payload: dict) -> dict:
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
        try:
            raw_response = await self.ai_service.generate_response(
                [
                    {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
                    {
                        "role": "user",
                        "content": self._turn_payload(user_message, assistant_message),
                    },
                ]
            )
        except Exception:
            return []

        extraction_payload = self._parse_extraction_payload(raw_response)
        candidates = extraction_payload["memories"]
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
                    "extraction_kind": "long_term_memory",
                    "extraction_rationale": normalized["rationale"],
                }
            )

        structured_memories = await self._save_structured_memories(
            extraction_payload["structured_memories"],
            conversation_id=conversation_id,
            user_message_id=str(user_message.get("id"))
            if user_message.get("id")
            else None,
        )
        saved_memories.extend(structured_memories)

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
        return self._parse_extraction_payload(raw_response)["memories"]

    def _parse_extraction_payload(self, raw_response: str) -> dict[str, Any]:
        try:
            payload = self._extract_json_payload(raw_response)
            data = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return {"memories": [], "structured_memories": {}}

        if isinstance(data, list):
            candidates = data
            structured_memories = {}
        elif isinstance(data, dict):
            candidates = data.get("memories", [])
            structured_memories = data.get("structured_memories", {})
        else:
            return {"memories": [], "structured_memories": {}}

        if not isinstance(structured_memories, dict):
            structured_memories = {}

        normalized_structured = {
            section: [
                candidate
                for candidate in structured_memories.get(section, [])
                if isinstance(candidate, dict)
            ]
            for section in VALID_STRUCTURED_SECTIONS
            if isinstance(structured_memories.get(section, []), list)
        }

        return {
            "memories": [
                candidate
                for candidate in candidates
                if isinstance(candidate, dict)
            ],
            "structured_memories": normalized_structured,
        }

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

    async def _save_structured_memories(
        self,
        structured_memories: dict[str, list[dict]],
        *,
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> list[dict]:
        saved: list[dict] = []

        for candidate in structured_memories.get("entities", []):
            normalized = self._normalize_entity_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_entity = await self._call_optional_store_method(
                "create_entity",
                normalized["payload"],
            )
            if saved_entity:
                saved.append(
                    self._saved_structured_result(
                        saved_entity,
                        "entity",
                        normalized["rationale"],
                    )
                )

        for candidate in structured_memories.get("entity_events", []):
            normalized = self._normalize_entity_event_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_event = await self._call_optional_store_method(
                "create_entity_event",
                normalized["payload"],
            )
            if saved_event:
                saved.append(
                    self._saved_structured_result(
                        saved_event,
                        "entity_event",
                        normalized["rationale"],
                    )
                )

        for candidate in structured_memories.get("personal_rules", []):
            normalized = self._normalize_rule_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_rule = await self._call_optional_store_method(
                "create_personal_rule",
                normalized["payload"],
            )
            if saved_rule:
                saved.append(
                    self._saved_structured_result(
                        saved_rule,
                        "personal_rule",
                        normalized["rationale"],
                    )
                )

        for candidate in structured_memories.get("plans", []):
            normalized = self._normalize_plan_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_plan = await self._call_optional_store_method(
                "create_plan",
                normalized["payload"],
            )
            if saved_plan:
                saved.append(
                    self._saved_structured_result(
                        saved_plan,
                        "plan",
                        normalized["rationale"],
                    )
                )

        for candidate in structured_memories.get("plan_milestones", []):
            normalized = self._normalize_plan_milestone_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_milestone = await self._call_optional_store_method(
                "create_plan_milestone",
                normalized["payload"],
            )
            if saved_milestone:
                saved.append(
                    self._saved_structured_result(
                        saved_milestone,
                        "plan_milestone",
                        normalized["rationale"],
                    )
                )

        for candidate in structured_memories.get("commitments", []):
            normalized = self._normalize_commitment_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_commitment = await self._call_optional_store_method(
                "create_commitment",
                normalized["payload"],
            )
            if saved_commitment:
                saved.append(
                    self._saved_structured_result(
                        saved_commitment,
                        "commitment",
                        normalized["rationale"],
                    )
                )

        return saved

    def _normalize_entity_candidate(
        self,
        candidate: dict,
        *,
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> Optional[dict]:
        importance = self._candidate_importance(candidate)
        entity_type = str(candidate.get("entity_type", "")).strip().lower()
        display_name = self._clean_text(candidate.get("display_name"))
        summary = self._clean_text(candidate.get("summary"))
        relationship = self._clean_text(candidate.get("relationship"))
        rationale = self._clean_text(candidate.get("rationale"))

        if importance is None or importance < MIN_IMPORTANCE_TO_SAVE:
            return None
        if entity_type not in EntityType.__args__:
            return None
        if (
            not display_name
            or len(display_name) < 2
            or self._looks_noisy(display_name)
            or self._looks_like_vague_entity(display_name)
        ):
            return None

        try:
            payload = EntityCreateRequest(
                entity_type=entity_type,
                display_name=display_name,
                normalized_name=self._normalized_text(
                    candidate.get("normalized_name") or display_name
                ),
                aliases=self._clean_list(candidate.get("aliases")),
                relationship=relationship,
                summary=summary,
                source_conversation_id=conversation_id,
                source_message_id=user_message_id,
                importance=importance,
                metadata={"extraction_rationale": rationale or "Useful named context."},
            ).model_dump(exclude_none=True)
        except Exception:
            return None
        return {"payload": payload, "rationale": rationale or "Useful named context."}

    def _normalize_entity_event_candidate(
        self,
        candidate: dict,
        *,
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> Optional[dict]:
        importance = self._candidate_importance(candidate)
        entity_id = self._clean_text(candidate.get("entity_id"))
        event_type = str(candidate.get("event_type", "note")).strip().lower() or "note"
        title = self._clean_text(candidate.get("title"))
        content = self._clean_text(candidate.get("content"))
        rationale = self._clean_text(candidate.get("rationale"))

        if importance is None or importance < MIN_IMPORTANCE_TO_SAVE:
            return None
        if not entity_id:
            return None
        if not content or self._looks_noisy(content):
            return None

        try:
            payload = EntityEventCreateRequest(
                entity_id=entity_id,
                event_type=event_type,
                title=title,
                content=content,
                source_conversation_id=conversation_id,
                source_message_id=user_message_id,
                importance=importance,
                metadata={
                    "entity_name": self._clean_text(candidate.get("entity_name")),
                    "extraction_rationale": rationale or "Useful entity event.",
                },
            ).model_dump(exclude_none=True)
        except Exception:
            return None
        return {"payload": payload, "rationale": rationale or "Useful entity event."}

    def _normalize_rule_candidate(
        self,
        candidate: dict,
        *,
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> Optional[dict]:
        priority = self._candidate_importance(candidate, field_name="priority")
        rule_type = str(candidate.get("rule_type", "")).strip().lower()
        title = self._clean_text(candidate.get("title"))
        rule_text = self._clean_text(candidate.get("rule_text"))
        rationale = self._clean_text(candidate.get("rationale"))

        if priority is None or priority < MIN_IMPORTANCE_TO_SAVE:
            return None
        if rule_type not in RuleType.__args__:
            return None
        if not title or not rule_text or self._looks_noisy(rule_text):
            return None

        try:
            payload = PersonalRuleCreateRequest(
                rule_type=rule_type,
                title=title,
                rule_text=rule_text,
                trigger_keywords=self._clean_list(candidate.get("trigger_keywords")),
                source_conversation_id=conversation_id,
                source_message_id=user_message_id,
                priority=priority,
                metadata={"extraction_rationale": rationale or "Useful personal rule."},
            ).model_dump(exclude_none=True)
        except Exception:
            return None
        return {"payload": payload, "rationale": rationale or "Useful personal rule."}

    def _normalize_plan_candidate(
        self,
        candidate: dict,
        *,
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> Optional[dict]:
        priority = self._candidate_importance(candidate, field_name="priority")
        plan_type = str(candidate.get("plan_type", "")).strip().lower()
        title = self._clean_text(candidate.get("title"))
        description = self._clean_text(candidate.get("description"))
        desired_outcome = self._clean_text(candidate.get("desired_outcome"))
        rationale = self._clean_text(candidate.get("rationale"))

        if priority is None or priority < MIN_IMPORTANCE_TO_SAVE:
            return None
        if plan_type not in PlanType.__args__:
            return None
        if not title or self._looks_noisy(title):
            return None

        try:
            payload = PlanCreateRequest(
                plan_type=plan_type,
                title=title,
                description=description,
                desired_outcome=desired_outcome,
                source_conversation_id=conversation_id,
                source_message_id=user_message_id,
                priority=priority,
                metadata={"extraction_rationale": rationale or "Useful plan context."},
            ).model_dump(exclude_none=True)
        except Exception:
            return None
        return {"payload": payload, "rationale": rationale or "Useful plan context."}

    def _normalize_plan_milestone_candidate(
        self,
        candidate: dict,
        *,
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> Optional[dict]:
        priority = self._candidate_importance(candidate, field_name="priority")
        plan_id = self._clean_text(candidate.get("plan_id"))
        title = self._clean_text(candidate.get("title"))
        description = self._clean_text(candidate.get("description"))
        milestone_type = (
            str(candidate.get("milestone_type", "checkpoint")).strip().lower()
            or "checkpoint"
        )
        target_date = self._clean_text(candidate.get("target_date"))
        rationale = self._clean_text(candidate.get("rationale"))

        if priority is None or priority < MIN_IMPORTANCE_TO_SAVE:
            return None
        if not plan_id:
            return None
        if not title or self._looks_noisy(title):
            return None

        try:
            payload = PlanMilestoneCreateRequest(
                plan_id=plan_id,
                title=title,
                description=description,
                milestone_type=milestone_type,
                target_date=target_date,
                source_conversation_id=conversation_id,
                source_message_id=user_message_id,
                priority=priority,
                metadata={
                    "plan_title": self._clean_text(candidate.get("plan_title")),
                    "extraction_rationale": rationale or "Useful plan milestone.",
                },
            ).model_dump(exclude_none=True)
        except Exception:
            return None
        return {"payload": payload, "rationale": rationale or "Useful plan milestone."}

    def _normalize_commitment_candidate(
        self,
        candidate: dict,
        *,
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> Optional[dict]:
        priority = self._candidate_importance(candidate, field_name="priority")
        commitment_type = str(candidate.get("commitment_type", "")).strip().lower()
        title = self._clean_text(candidate.get("title"))
        commitment_text = self._clean_text(candidate.get("commitment_text"))
        due_at = self._clean_text(candidate.get("due_at"))
        rationale = self._clean_text(candidate.get("rationale"))

        if priority is None or priority < MIN_IMPORTANCE_TO_SAVE:
            return None
        if commitment_type not in CommitmentType.__args__:
            return None
        if not title or not commitment_text or self._looks_noisy(commitment_text):
            return None

        try:
            payload = CommitmentCreateRequest(
                commitment_type=commitment_type,
                title=title,
                commitment_text=commitment_text,
                source_conversation_id=conversation_id,
                source_message_id=user_message_id,
                priority=priority,
                due_at=due_at,
                metadata={"extraction_rationale": rationale or "Useful commitment."},
            ).model_dump(exclude_none=True)
        except Exception:
            return None
        return {"payload": payload, "rationale": rationale or "Useful commitment."}

    def _candidate_importance(
        self,
        candidate: dict,
        *,
        field_name: str = "importance",
    ) -> Optional[int]:
        try:
            importance = int(candidate.get(field_name, candidate.get("importance", 0)))
        except (TypeError, ValueError):
            return None
        if importance > 5:
            return None
        return importance

    async def _call_optional_store_method(
        self,
        method_name: str,
        payload: dict,
    ) -> Optional[dict]:
        method = getattr(self.memory_service, method_name, None)
        if method is None:
            return None
        try:
            return await method(payload)
        except Exception:
            return None

    def _saved_structured_result(
        self,
        saved: dict,
        structured_type: str,
        rationale: str,
    ) -> dict:
        return {
            **saved,
            "extraction_kind": "structured_memory",
            "structured_type": structured_type,
            "extraction_rationale": rationale,
        }

    def _clean_text(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None

    def _clean_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned_values = []
        seen = set()
        for item in value:
            cleaned = self._clean_text(item)
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned_values.append(cleaned)
        return cleaned_values

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

    def _looks_like_vague_entity(self, display_name: str) -> bool:
        normalized = self._normalized_text(display_name)
        vague_names = {
            "someone",
            "somebody",
            "a girl",
            "the girl",
            "a guy",
            "the guy",
            "work",
            "money",
            "budget",
            "thing",
        }
        return normalized in vague_names

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

    def _normalized_text(self, text: Any) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))
