import json
import re
from difflib import SequenceMatcher
from typing import Any, Optional, Protocol

from app.models.commitment import CommitmentCreateRequest, CommitmentType
from app.models.entity import EntityCreateRequest, EntityEventCreateRequest, EntityType
from app.models.memory_candidate import MemoryCandidateCreateRequest
from app.models.memory_discipline import (
    MemoryCandidateKind,
    MemoryDisciplineAction,
    MemoryDisciplineCandidate,
    MemoryDisciplineDecision,
)
from app.models.personal_rule import PersonalRuleCreateRequest, RuleType
from app.models.plan import PlanCreateRequest, PlanMilestoneCreateRequest, PlanType
from app.services.ai_service import AIService
from app.services.commitment_service import CommitmentService
from app.services.entity_normalization_service import EntityNormalizationService
from app.services.entity_service import EntityService
from app.services.memory_discipline_service import MemoryDisciplineService
from app.services.plan_service import PlanService
from app.services.rule_service import RuleService

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
        "primary_entity_id": "only include if already known",
        "entity_name": "specific person name if this plan is about someone and ID is unknown",
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
        "plan_id": "only include if already known",
        "milestone_id": "only include if already known",
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
- corrections to prior memory: "her name is Melissa, not Al", "I live in Massachusetts, not Europe"

Plan rules:
- Only create a top-level plan for a durable, multi-step goal that should remain useful for weeks or months.
- Do not create a new top-level plan for every update, reflection, chat summary, or small next step.
- If the user gives progress, details, a date, a follow-up task, or a sub-goal for an existing plan, prefer a plan_milestone or commitment.
- Treat related details as part of a larger plan when possible: income targets can belong under a relocation or freedom plan; app launch details can belong under a development roadmap; date logistics can belong under one dating plan for that person.
- Avoid multiple active plans that mean the same thing with different wording.

Plan intelligence rules:
- A top-level plan is a durable container for a major area of life or work.
- Do not create a new top-level plan for progress updates, repeated goals, deadlines, single next actions, or alternate wording.
- If a candidate belongs under an active plan, output it as a plan_milestone or commitment instead.
- Income, savings, client acquisition, and app revenue details should attach to the user's broader life/work plan when related.
- Date logistics for the same person should attach to one dating plan for that person.
- When unsure, prefer a milestone/commitment or ask for confirmation instead of creating a duplicate plan.

Correction rules:
- If the user corrects stale or wrong information, treat the corrected value as high-priority durable memory.
- When the user says "not X, actually Y", do not save X as current truth. Save Y clearly and include the correction in the memory content.
- For corrected person names, create or update the corrected person entity and add a relationship_update entity event that says the earlier name or label was wrong.
- For corrected plans, save the updated plan details with the corrected person/place/date and avoid reinforcing stale plan wording.
- For corrected project names, use EchoDesk and FlowForce as canonical project names. Do not save Flow, Flowfirst, Flowforte, or Echotask as active project names or aliases.

Entity normalization rules:
- If the user corrects a name, spelling, identity, relationship, or label, treat the corrected value as canonical.
- Do not save the wrong value as current truth or as an active alias when the user asked to remove it.
- Before creating a new entity, check whether the name is an alias, obsolete name, spelling variant, or correction of an existing active entity.
- If an obsolete name appears in a new candidate, rewrite it to the canonical entity name and link to the canonical entity.

Correction execution rules:
- If the user explicitly corrects memory, do not just acknowledge it.
- Apply the correction to active structured memory.
- Archive or mark obsolete the wrong record when keeping it active would confuse future retrieval.
- Update the correct record with the new durable detail.
- Do not create a new duplicate record as the correction mechanism.
- After applying the change, summarize exactly what was archived, updated, merged, or created.

Memory Discipline rules:
- Prefer updating existing memory over creating new memory.
- Before saving a plan, goal, rule, task, or entity, consider whether it belongs to an active existing record.
- Corrections from the user override prior memory.
- A duplicate active plan/rule/entity is a memory quality error.
- Use top-level plans only for durable major areas.
- Use milestones only for achievement checkpoints that would make sense as
  completed badges/trophies: launches, approvals, submissions, completed
  applications, secured money, or measurable thresholds.
- Do not use milestones for alternate plan titles, broad strategy, exploratory
  questions, repeated dating logistics, or chat fragments.
- Use commitments for concrete actions, habits, or checklist items.
- Use entity events for relationship changes, interactions, or historical notes.
- Use plan descriptions for strategy, routes, success criteria, and background
  context that guides the plan.
- Never preserve stale wrong names as current truth.

Do not extract:
- one-off emotions without durable context
- generic requests or instructions to answer the current question
- assistant advice
- assistant summaries or assistant claims that something was saved, fixed, updated, or archived
- duplicates of existing memories
- private sensitive details unless the user clearly stated them as personal context
- vague entities like "someone", "a girl", "work", or "money" unless named or clearly durable

Use importance:
1-2 = weak/noisy, usually do not save
3 = useful context
4 = important recurring context
5 = critical identity, legal, financial, health, relationship, or life context

If there is nothing worth remembering, return {"memories": [], "structured_memories": {}}.

Important save discipline:
- Treat the assistant response as non-authoritative context only.
- Durable memory must be proposed as a pending candidate before it can be saved.
- Extract durable truth only from user-stated facts, user corrections, or confirmed backend operation results.
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

    async def update_long_term_memory(
        self,
        memory_id: str,
        memory_type: Optional[str] = None,
        content: Optional[str] = None,
        importance: Optional[int] = None,
        active: Optional[bool] = None,
    ) -> Optional[dict]:
        pass

    async def deactivate_long_term_memory(self, memory_id: str) -> bool:
        pass

    async def create_memory_correction(self, correction: dict) -> dict:
        pass

    async def create_entity(self, payload: dict) -> dict:
        pass

    async def list_entities(
        self,
        limit: int = 50,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        normalized_name: Optional[str] = None,
    ) -> list[dict]:
        pass

    async def create_entity_event(self, payload: dict) -> dict:
        pass

    async def create_personal_rule(self, payload: dict) -> dict:
        pass

    async def update_personal_rule(self, rule_id: str, **updates: object) -> dict:
        pass

    async def create_plan(self, payload: dict) -> dict:
        pass

    async def list_plans(
        self,
        limit: int = 50,
        plan_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        pass

    async def create_plan_milestone(self, payload: dict) -> dict:
        pass

    async def create_commitment(self, payload: dict) -> dict:
        pass

    async def create_memory_candidate(self, payload: dict) -> dict:
        pass


class MemoryExtractionService:
    def __init__(
        self,
        ai_service: AIService,
        memory_service: MemoryStore,
        memory_discipline_service: Optional[MemoryDisciplineService] = None,
    ) -> None:
        self.ai_service = ai_service
        self.memory_service = memory_service
        self.entity_service = EntityService(memory_service)
        self.rule_service = RuleService(memory_service)
        self.plan_service = PlanService(memory_service)
        self.commitment_service = CommitmentService(memory_service)
        self.entity_normalization_service = EntityNormalizationService()
        self.memory_discipline_service = (
            memory_discipline_service or MemoryDisciplineService(memory_service)
        )

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
        pending_candidates = []

        for candidate in candidates:
            normalized = self._normalize_candidate(candidate)
            if normalized is None:
                continue
            if await self._is_duplicate(normalized["content"]):
                continue

            pending = await self._create_pending_memory_candidate(
                candidate_type="long_term_memory",
                payload={
                    "memory_type": normalized["memory_type"],
                    "content": normalized["content"],
                    "importance": normalized["importance"],
                    "metadata": {
                        "extraction_rationale": normalized["rationale"],
                    },
                },
                rationale=normalized["rationale"],
                conversation_id=conversation_id,
                user_message_id=str(user_message.get("id"))
                if user_message.get("id")
                else None,
                risk_level=self._candidate_risk_level(
                    candidate_type="long_term_memory",
                    payload=normalized,
                ),
            )
            if pending:
                pending_candidates.append(pending)

        structured_memories = await self._save_structured_memories(
            extraction_payload["structured_memories"],
            conversation_id=conversation_id,
            user_message_id=str(user_message.get("id"))
            if user_message.get("id")
            else None,
        )
        pending_candidates.extend(structured_memories)

        return pending_candidates

    def _turn_payload(self, user_message: dict, assistant_message: dict) -> str:
        return json.dumps(
            {
                "user_message": str(user_message.get("content", "")),
                "assistant_response_context_only": str(
                    assistant_message.get("content", "")
                ),
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
        entity_ids_by_key: dict[str, str] = {}
        plan_ids_by_key: dict[str, str] = {}
        await self._load_existing_entity_keys(entity_ids_by_key)
        await self._load_existing_plan_keys(plan_ids_by_key)

        for candidate in structured_memories.get("entities", []):
            normalized = self._normalize_entity_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_entity = await self._save_structured_candidate(
                kind=MemoryCandidateKind.ENTITY,
                payload=normalized["payload"],
                structured_type="entity",
                rationale=normalized["rationale"],
                fallback=lambda: self._call_service_create(
                    self.entity_service.create_entity,
                    EntityCreateRequest(**normalized["payload"]),
                ),
            )
            if saved_entity:
                saved.append(saved_entity)

        for candidate in structured_memories.get("entity_events", []):
            await self._resolve_entity_reference(candidate, entity_ids_by_key)
            normalized = self._normalize_entity_event_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_event = await self._create_pending_memory_candidate(
                candidate_type="entity_event",
                payload=normalized["payload"],
                rationale=normalized["rationale"],
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                risk_level=self._candidate_risk_level(
                    candidate_type="entity_event",
                    payload=normalized["payload"],
                ),
            )
            if saved_event:
                saved.append(saved_event)

        for candidate in structured_memories.get("personal_rules", []):
            normalized = self._normalize_rule_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_rule = await self._save_structured_candidate(
                kind=MemoryCandidateKind.PERSONAL_RULE,
                payload=normalized["payload"],
                structured_type="personal_rule",
                rationale=normalized["rationale"],
                fallback=lambda: self._call_service_create(
                    self.rule_service.create_rule,
                    PersonalRuleCreateRequest(**normalized["payload"]),
                ),
            )
            if saved_rule:
                saved.append(saved_rule)

        for candidate in structured_memories.get("plans", []):
            await self._resolve_entity_reference(candidate, entity_ids_by_key)
            normalized = self._normalize_plan_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_plan = await self._save_structured_candidate(
                kind=MemoryCandidateKind.PLAN,
                payload=normalized["payload"],
                structured_type="plan",
                rationale=normalized["rationale"],
                fallback=lambda: self._call_service_create(
                    self.plan_service.create_plan,
                    PlanCreateRequest(**normalized["payload"]),
                ),
            )
            if saved_plan:
                saved.append(saved_plan)

        for candidate in structured_memories.get("plan_milestones", []):
            await self._resolve_plan_reference(candidate, plan_ids_by_key)
            normalized = self._normalize_plan_milestone_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_milestone = await self._save_structured_candidate(
                kind=MemoryCandidateKind.PLAN_MILESTONE,
                payload=normalized["payload"],
                structured_type="plan_milestone",
                rationale=normalized["rationale"],
                fallback=lambda: self._call_service_create(
                    self.plan_service.create_milestone,
                    PlanMilestoneCreateRequest(**normalized["payload"]),
                ),
            )
            if saved_milestone:
                saved.append(saved_milestone)

        for candidate in structured_memories.get("commitments", []):
            await self._resolve_entity_reference(candidate, entity_ids_by_key)
            await self._resolve_plan_reference(candidate, plan_ids_by_key)
            normalized = self._normalize_commitment_candidate(
                candidate,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
            )
            if normalized is None:
                continue
            saved_commitment = await self._save_structured_candidate(
                kind=MemoryCandidateKind.COMMITMENT,
                payload=normalized["payload"],
                structured_type="commitment",
                rationale=normalized["rationale"],
                fallback=lambda: self._call_service_create(
                    self.commitment_service.create_commitment,
                    CommitmentCreateRequest(**normalized["payload"]),
                ),
            )
            if saved_commitment:
                saved.append(saved_commitment)

        return saved

    async def _upsert_corrected_memory(
        self,
        normalized: dict,
        *,
        conversation_id: str,
        user_message_id: Optional[str],
        source_text: str = "",
        structured_memories: Optional[dict[str, list[dict]]] = None,
    ) -> Optional[dict]:
        correction_source = f"{normalized['content']} {source_text}".strip()
        correction = self._correction_terms(correction_source)
        if correction is None:
            return None

        existing_memories = await self.memory_service.get_relevant_memories(
            query=correction_source,
            limit=20,
        )
        stale_memories = [
            memory
            for memory in existing_memories
            if self._is_stale_corrected_memory(memory, correction)
        ]
        if not stale_memories:
            return None

        update_method = getattr(self.memory_service, "update_long_term_memory", None)
        deactivate_method = getattr(
            self.memory_service,
            "deactivate_long_term_memory",
            None,
        )
        correction_group = self._correction_group(correction)
        corrected_metadata = {
            **(stale_memories[0].get("metadata") or {}),
            "correction": {
                "old_values": sorted(correction["wrong"]),
                "new_values": sorted(correction["corrected"]),
                "previous_content": stale_memories[0].get("content"),
                "source_message_id": user_message_id,
            },
        }

        updated_memory = None
        if update_method is not None:
            try:
                updated_memory = await update_method(
                    stale_memories[0]["id"],
                    memory_type=normalized["memory_type"],
                    content=normalized["content"],
                    importance=normalized["importance"],
                    active=True,
                    confidence=0.9,
                    correction_group=correction_group,
                    metadata=corrected_metadata,
                )
            except Exception:
                updated_memory = None

        if updated_memory is not None and update_method is not None:
            for stale_memory in stale_memories[1:]:
                try:
                    await update_method(
                        stale_memory["id"],
                        active=False,
                        superseded_by=updated_memory.get("id"),
                        correction_group=correction_group,
                        metadata={
                            **(stale_memory.get("metadata") or {}),
                            "superseded_by_correction": {
                                "replacement_memory_id": updated_memory.get("id"),
                                "old_values": sorted(correction["wrong"]),
                                "new_values": sorted(correction["corrected"]),
                                "source_message_id": user_message_id,
                            },
                        },
                    )
                except Exception:
                    if deactivate_method is not None:
                        try:
                            await deactivate_method(stale_memory["id"])
                        except Exception:
                            continue
        elif deactivate_method is not None:
            start_index = 1 if updated_memory is not None else 0
            for stale_memory in stale_memories[start_index:]:
                try:
                    await deactivate_method(stale_memory["id"])
                except Exception:
                    continue

        if updated_memory is None:
            return None

        await self._record_memory_correction(
            correction=correction,
            normalized=normalized,
            updated_memory=updated_memory,
            stale_memories=stale_memories,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
        )
        await self._save_person_correction_context(
            correction=correction,
            normalized=normalized,
            source_text=source_text,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            structured_memories=structured_memories or {},
        )

        return {
            **updated_memory,
            "source_conversation_id": updated_memory.get("source_conversation_id")
            or conversation_id,
            "source_message_id": updated_memory.get("source_message_id")
            or user_message_id,
            "extraction_kind": "long_term_memory",
            "extraction_action": "updated_correction",
            "extraction_rationale": normalized["rationale"],
        }

    async def _record_memory_correction(
        self,
        *,
        correction: dict[str, set[str]],
        normalized: dict,
        updated_memory: dict,
        stale_memories: list[dict],
        conversation_id: str,
        user_message_id: Optional[str],
    ) -> None:
        create_correction = getattr(self.memory_service, "create_memory_correction", None)
        if create_correction is None:
            return

        wrong_values = sorted(correction["wrong"])
        corrected_values = sorted(correction["corrected"])
        old_value = ", ".join(wrong_values) if wrong_values else None
        new_value = (
            ", ".join(corrected_values)
            if corrected_values
            else normalized["content"]
        )
        payload = {
            "correction_type": self._correction_type(normalized["content"]),
            "old_value": old_value,
            "new_value": new_value,
            "target_table": "long_term_memory",
            "target_id": updated_memory.get("id"),
            "source_conversation_id": conversation_id,
            "source_message_id": user_message_id,
            "applied": True,
            "confidence": 0.9,
            "metadata": {
                "correction_group": self._correction_group(correction),
                "updated_memory_id": updated_memory.get("id"),
                "stale_memory_ids": [
                    memory.get("id")
                    for memory in stale_memories
                    if memory.get("id")
                ],
                "corrected_content": normalized["content"],
                "rationale": normalized.get("rationale"),
            },
        }
        try:
            await create_correction(payload)
        except Exception:
            return

    def _correction_group(self, correction: dict[str, set[str]]) -> str:
        wrong = "-".join(sorted(correction["wrong"])) or "unknown"
        corrected = "-".join(sorted(correction["corrected"])) or "unknown"
        return f"correction:{wrong}->{corrected}"

    async def _save_person_correction_context(
        self,
        *,
        correction: dict[str, set[str]],
        normalized: dict,
        source_text: str,
        conversation_id: str,
        user_message_id: Optional[str],
        structured_memories: dict[str, list[dict]],
    ) -> None:
        if not self._looks_like_person_name_correction(
            normalized["content"],
            source_text,
        ):
            return
        corrected_name = self._person_name_from_correction(correction)
        if not corrected_name:
            return
        structured_event_exists = self._structured_memories_cover_person_correction(
            structured_memories,
            correction,
            corrected_name,
        )

        wrong_names = sorted(correction["wrong"])
        wrong_display = ", ".join(name.title() for name in wrong_names)
        corrected_display = corrected_name.title()
        summary = (
            f"{corrected_display} is the corrected person reference"
            + (f" replacing {wrong_display}." if wrong_display else ".")
        )

        try:
            entity = await self.entity_service.create_entity(
                EntityCreateRequest(
                    entity_type="person",
                    display_name=corrected_display,
                    normalized_name=corrected_name,
                    summary=summary,
                    source_conversation_id=conversation_id,
                    source_message_id=user_message_id,
                    importance=max(int(normalized.get("importance", 3)), 4),
                    metadata={
                        "correction_source": "explicit_person_correction",
                        "wrong_names": wrong_names,
                    },
                )
            )
        except Exception:
            return

        entity_id = self._clean_text(entity.get("id"))
        if not entity_id:
            return

        if not structured_event_exists:
            content = (
                f"The prior name {wrong_display} was wrong; "
                f"the correct name is {corrected_display}."
                if wrong_display
                else f"The correct person name is {corrected_display}."
            )
            try:
                await self.entity_service.create_entity_event(
                    EntityEventCreateRequest(
                        entity_id=entity_id,
                        event_type="relationship_update",
                        title="Corrected name",
                        content=content,
                        source_conversation_id=conversation_id,
                        source_message_id=user_message_id,
                        importance=max(int(normalized.get("importance", 3)), 4),
                        metadata={
                            "correction_type": "entity_name",
                            "wrong_names": wrong_names,
                            "corrected_name": corrected_name,
                        },
                    )
                )
            except Exception:
                return

        await self._link_corrected_person_to_plans(
            entity_id=entity_id,
            corrected_name=corrected_name,
            wrong_names=wrong_names,
        )

    async def _link_corrected_person_to_plans(
        self,
        *,
        entity_id: str,
        corrected_name: str,
        wrong_names: list[str],
    ) -> None:
        list_plans = getattr(self.memory_service, "list_plans", None)
        update_plan = getattr(self.memory_service, "update_plan", None)
        if list_plans is None or update_plan is None:
            return
        try:
            plans = await list_plans(active=True, limit=100)
        except Exception:
            return

        for plan in plans:
            updates = self._corrected_person_plan_updates(
                plan,
                entity_id=entity_id,
                corrected_name=corrected_name,
                wrong_names=wrong_names,
            )
            if not updates:
                continue
            try:
                await update_plan(plan["id"], **updates)
            except Exception:
                continue

    def _corrected_person_plan_updates(
        self,
        plan: dict[str, Any],
        *,
        entity_id: str,
        corrected_name: str,
        wrong_names: list[str],
    ) -> dict[str, Any]:
        text = self._normalized_text(
            " ".join(
                str(plan.get(field) or "")
                for field in ("title", "description", "desired_outcome")
            )
        )
        if not any(wrong in set(text.split()) for wrong in wrong_names):
            return {}

        corrected_display = corrected_name.title()
        updates: dict[str, Any] = {"primary_entity_id": entity_id}
        for field in ("title", "description", "desired_outcome"):
            corrected_value = self._replace_terms(
                plan.get(field),
                replacements={
                    wrong: corrected_display
                    for wrong in wrong_names
                },
            )
            if corrected_value is not None and corrected_value != plan.get(field):
                updates[field] = corrected_value

        metadata = {
            **(plan.get("metadata") or {}),
            "person_correction": {
                "corrected_name": corrected_name,
                "wrong_names": wrong_names,
            },
        }
        if metadata != (plan.get("metadata") or {}):
            updates["metadata"] = metadata

        return updates

    def _replace_terms(
        self,
        value: Any,
        *,
        replacements: dict[str, str],
    ) -> Optional[str]:
        cleaned = self._clean_text(value)
        if cleaned is None:
            return None
        updated = cleaned
        for wrong, corrected in replacements.items():
            updated = re.sub(
                rf"\b{re.escape(wrong)}\b",
                corrected,
                updated,
                flags=re.I,
            )
        return updated

    def _looks_like_person_name_correction(
        self,
        content: str,
        source_text: str,
    ) -> bool:
        normalized = self._normalized_text(f"{content} {source_text}")
        tokens = set(normalized.split())
        return bool(
            tokens
            & {
                "name",
                "named",
                "person",
                "woman",
                "girl",
                "guy",
                "man",
                "her",
                "his",
            }
        )

    def _person_name_from_correction(
        self,
        correction: dict[str, set[str]],
    ) -> Optional[str]:
        ignored = {
            "ai",
            "al",
            "girl",
            "guy",
            "her",
            "him",
            "his",
            "name",
            "person",
            "woman",
        }
        candidates = [
            term
            for term in sorted(correction["corrected"])
            if term not in ignored and re.fullmatch(r"[a-z][a-z0-9]{1,24}", term)
        ]
        if len(candidates) != 1:
            return None
        return candidates[0]

    def _structured_memories_cover_person_correction(
        self,
        structured_memories: dict[str, list[dict]],
        correction: dict[str, set[str]],
        corrected_name: str,
    ) -> bool:
        wrong_terms = correction["wrong"]
        for event in structured_memories.get("entity_events", []):
            text = self._normalized_text(
                " ".join(
                    str(event.get(field) or "")
                    for field in ("title", "content", "entity_name")
                )
            )
            terms = set(text.split())
            if corrected_name in terms and terms.intersection(wrong_terms):
                return True

        return False

    def _correction_type(self, content: str) -> str:
        terms = self._normalized_text(content).split()
        term_set = set(terms)
        if term_set & {"live", "lives", "living", "location", "state", "timezone"}:
            return "location"
        if term_set & {"date", "dinner", "plan", "restaurant", "monday"}:
            return "plan_detail"
        if term_set & {"rule", "budget", "spending", "doordash", "uber"}:
            return "rule_detail"
        if term_set & {"prefer", "preference"}:
            return "preference"
        if term_set & {"name", "named", "person", "woman", "girl"}:
            return "entity_name"
        return "other"

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
        primary_entity_id = self._clean_text(
            candidate.get("primary_entity_id") or candidate.get("entity_id")
        )
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
                primary_entity_id=primary_entity_id,
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
        entity_id = self._clean_text(candidate.get("entity_id"))
        plan_id = self._clean_text(candidate.get("plan_id"))
        milestone_id = self._clean_text(candidate.get("milestone_id"))

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
                entity_id=entity_id,
                plan_id=plan_id,
                milestone_id=milestone_id,
                source_conversation_id=conversation_id,
                source_message_id=user_message_id,
                priority=priority,
                due_at=due_at,
                metadata={"extraction_rationale": rationale or "Useful commitment."},
            ).model_dump(exclude_none=True)
        except Exception:
            return None
        return {"payload": payload, "rationale": rationale or "Useful commitment."}

    def _remember_entity_keys(
        self,
        entity: dict[str, Any],
        entity_ids_by_key: dict[str, str],
    ) -> None:
        entity_id = self._clean_text(entity.get("id"))
        if not entity_id:
            return
        values = [
            entity.get("display_name"),
            entity.get("normalized_name"),
            *entity.get("aliases", []),
        ]
        for value in values:
            key = self._normalized_text(value)
            if key:
                entity_ids_by_key[key] = entity_id

    def _remember_plan_keys(
        self,
        plan: dict[str, Any],
        plan_ids_by_key: dict[str, str],
    ) -> None:
        plan_id = self._clean_text(plan.get("id"))
        if not plan_id:
            return
        for value in (plan.get("title"), plan.get("description")):
            key = self._normalized_text(value)
            if key:
                plan_ids_by_key[key] = plan_id

    async def _load_existing_entity_keys(
        self,
        entity_ids_by_key: dict[str, str],
    ) -> None:
        method = getattr(self.memory_service, "list_entities", None)
        if method is None:
            return
        try:
            entities = await method(active=True, limit=100)
        except Exception:
            return
        for entity in entities:
            self._remember_entity_keys(entity, entity_ids_by_key)

    async def _load_existing_plan_keys(
        self,
        plan_ids_by_key: dict[str, str],
    ) -> None:
        method = getattr(self.memory_service, "list_plans", None)
        if method is None:
            return
        try:
            plans = await method(active=True, limit=100)
        except Exception:
            return
        for plan in plans:
            self._remember_plan_keys(plan, plan_ids_by_key)

    async def _resolve_entity_reference(
        self,
        candidate: dict[str, Any],
        entity_ids_by_key: dict[str, str],
    ) -> None:
        if self._clean_text(candidate.get("entity_id")):
            return
        entity_name = self._clean_text(candidate.get("entity_name"))
        if not entity_name:
            return

        entity_id = entity_ids_by_key.get(self._normalized_text(entity_name))
        if entity_id:
            candidate["entity_id"] = entity_id
            return

        existing = await self._find_existing_entity(entity_name)
        if existing:
            self._remember_entity_keys(existing, entity_ids_by_key)
            candidate["entity_id"] = existing.get("id")

    async def _resolve_plan_reference(
        self,
        candidate: dict[str, Any],
        plan_ids_by_key: dict[str, str],
    ) -> None:
        if self._clean_text(candidate.get("plan_id")):
            return
        plan_title = self._clean_text(candidate.get("plan_title"))
        if not plan_title:
            return

        plan_id = plan_ids_by_key.get(self._normalized_text(plan_title))
        if plan_id:
            candidate["plan_id"] = plan_id
            return

        existing = await self._find_existing_plan(plan_title)
        if existing:
            self._remember_plan_keys(existing, plan_ids_by_key)
            candidate["plan_id"] = existing.get("id")

    async def _find_existing_entity(self, entity_name: str) -> Optional[dict[str, Any]]:
        method = getattr(self.memory_service, "list_entities", None)
        if method is None:
            return None
        try:
            entities = await method(active=True, limit=100)
        except Exception:
            return None

        target = self._normalized_text(entity_name)
        obsolete_match = self.entity_normalization_service.detect_obsolete_alias(
            entity_name,
            entities,
        )
        if obsolete_match is not None:
            return obsolete_match
        for entity in entities:
            keys = [
                entity.get("normalized_name"),
                entity.get("display_name"),
                *entity.get("aliases", []),
            ]
            if target in {self._normalized_text(key) for key in keys if key}:
                return entity
        return None

    async def _find_existing_plan(self, plan_title: str) -> Optional[dict[str, Any]]:
        method = getattr(self.memory_service, "list_plans", None)
        if method is None:
            return None
        try:
            plans = await method(active=True, limit=100)
        except Exception:
            return None

        target = self._normalized_text(plan_title)
        for plan in plans:
            if target == self._normalized_text(plan.get("title")):
                return plan
        return None

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

    async def _save_structured_candidate(
        self,
        *,
        kind: MemoryCandidateKind,
        payload: dict,
        structured_type: str,
        rationale: str,
        fallback: Any,
    ) -> Optional[dict]:
        candidate = MemoryDisciplineCandidate(
            kind=kind,
            payload=payload,
            source_conversation_id=payload.get("source_conversation_id"),
            source_message_id=payload.get("source_message_id"),
            source_memory_id=payload.get("source_memory_id"),
        )
        try:
            decision = await self.memory_discipline_service.decide(candidate)
        except Exception:
            decision = None

        decision_kind = decision.candidate_kind if decision is not None else kind
        candidate_type = self._candidate_type_for_kind(decision_kind)
        if candidate_type is None:
            return None
        candidate_payload = dict(decision.payload if decision is not None else payload)
        if decision is not None:
            candidate_payload["memory_discipline"] = {
                "action": decision.action.value,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "target_table": decision.target_table,
                "target_id": decision.target_id,
                "requires_confirmation": decision.requires_confirmation,
            }
        return await self._create_pending_memory_candidate(
            candidate_type=candidate_type,
            payload=candidate_payload,
            rationale=rationale,
            conversation_id=str(payload.get("source_conversation_id") or ""),
            user_message_id=self._clean_text(payload.get("source_message_id")),
            risk_level=self._candidate_risk_level(
                candidate_type=candidate_type,
                payload=candidate_payload,
                decision=decision,
            ),
        )

    def _create_action_for_kind(
        self,
        kind: MemoryCandidateKind,
    ) -> Optional[MemoryDisciplineAction]:
        return {
            MemoryCandidateKind.ENTITY: MemoryDisciplineAction.CREATE_ENTITY,
            MemoryCandidateKind.PERSONAL_RULE: MemoryDisciplineAction.CREATE_RULE,
            MemoryCandidateKind.PLAN: MemoryDisciplineAction.CREATE_PLAN,
            MemoryCandidateKind.PLAN_MILESTONE: MemoryDisciplineAction.CREATE_MILESTONE,
            MemoryCandidateKind.COMMITMENT: MemoryDisciplineAction.CREATE_COMMITMENT,
        }.get(kind)

    def _candidate_type_for_kind(self, kind: MemoryCandidateKind) -> Optional[str]:
        return {
            MemoryCandidateKind.ENTITY: "entity",
            MemoryCandidateKind.PERSONAL_RULE: "personal_rule",
            MemoryCandidateKind.PLAN: "plan",
            MemoryCandidateKind.PLAN_MILESTONE: "plan_milestone",
            MemoryCandidateKind.COMMITMENT: "commitment",
        }.get(kind)

    async def _create_pending_memory_candidate(
        self,
        *,
        candidate_type: str,
        payload: dict[str, Any],
        rationale: str,
        conversation_id: str,
        user_message_id: Optional[str],
        risk_level: str,
    ) -> Optional[dict]:
        create_candidate = getattr(self.memory_service, "create_memory_candidate", None)
        if create_candidate is None:
            return None
        try:
            row = await create_candidate(
                MemoryCandidateCreateRequest(
                    candidate_type=candidate_type,
                    payload=payload,
                    risk_level=risk_level,
                    reason=rationale,
                    source_conversation_id=conversation_id,
                    source_message_id=user_message_id,
                ).model_dump(exclude_none=True)
            )
        except Exception:
            return None
        return {
            **payload,
            **row,
            "extraction_kind": "memory_candidate",
            "structured_type": candidate_type
            if candidate_type != "long_term_memory"
            else None,
            "memory_type": payload.get("memory_type")
            if candidate_type == "long_term_memory"
            else None,
            "extraction_action": "candidate_created",
            "extraction_rationale": rationale,
            "pending": True,
        }

    def _candidate_risk_level(
        self,
        *,
        candidate_type: str,
        payload: dict[str, Any],
        decision: Optional[MemoryDisciplineDecision] = None,
    ) -> str:
        if candidate_type in {"plan", "correction", "archive", "merge"}:
            return "high"
        if decision is not None and (
            decision.requires_confirmation
            or decision.target_id
            or decision.action.value.startswith(("archive", "update"))
        ):
            return "high"
        if candidate_type in {"commitment", "entity_event"}:
            return "low"
        if candidate_type == "long_term_memory":
            importance = int(payload.get("importance") or 3)
            return "high" if importance >= 5 else "medium"
        return "medium"

    async def _call_service_create(self, method: Any, request: Any) -> Optional[dict]:
        try:
            return await method(request)
        except Exception:
            return None

    def _saved_structured_result(
        self,
        saved: dict,
        structured_type: str,
        rationale: str,
        *,
        extraction_action: str = "create",
        discipline_decision: Optional[MemoryDisciplineDecision] = None,
    ) -> dict:
        result = {
            **saved,
            "extraction_kind": "structured_memory",
            "structured_type": structured_type,
            "extraction_action": extraction_action,
            "extraction_rationale": rationale,
        }
        if discipline_decision is not None:
            result["discipline_decision"] = {
                "action": discipline_decision.action.value,
                "reason": discipline_decision.reason,
                "confidence": discipline_decision.confidence,
                "target_table": discipline_decision.target_table,
                "target_id": discipline_decision.target_id,
                "requires_confirmation": discipline_decision.requires_confirmation,
            }
        return result

    def _structured_type_for_decision(
        self,
        decision: MemoryDisciplineDecision,
        default_type: str,
    ) -> str:
        action_to_type = {
            MemoryDisciplineAction.CREATE_ENTITY: "entity",
            MemoryDisciplineAction.UPDATE_ENTITY: "entity",
            MemoryDisciplineAction.CREATE_RULE: "personal_rule",
            MemoryDisciplineAction.UPDATE_RULE: "personal_rule",
            MemoryDisciplineAction.CREATE_PLAN: "plan",
            MemoryDisciplineAction.UPDATE_PLAN: "plan",
            MemoryDisciplineAction.CREATE_MILESTONE: "plan_milestone",
            MemoryDisciplineAction.UPDATE_MILESTONE: "plan_milestone",
            MemoryDisciplineAction.CREATE_COMMITMENT: "commitment",
            MemoryDisciplineAction.UPDATE_COMMITMENT: "commitment",
        }
        return action_to_type.get(decision.action, default_type)

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
            "girl from work",
            "the girl from work",
            "a guy",
            "the guy",
            "guy from work",
            "the guy from work",
            "coworker",
            "a coworker",
            "the coworker",
            "date",
            "my date",
            "dating interest",
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

    def _correction_terms(self, content: str) -> Optional[dict[str, set[str]]]:
        lowered = content.lower()
        if not any(
            term in lowered
            for term in (
                "not ",
                "wrong",
                "corrected from",
                "change",
                "replace",
                "update",
            )
        ):
            return None

        wrong_terms: set[str] = set()
        corrected_terms: set[str] = set()
        pair_patterns = (
            r"\b(?:change|update|replace)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9]{1,24})(?:\s+(?:memory|name|reference|plan|person))?\s+(?:to|for|with)\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bfrom\s+([A-Za-z][A-Za-z0-9]{1,24})\s+to\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
        )
        wrong_patterns = (
            r"\bnot\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bcorrected\s+from\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bcorrected\s+from\s+[A-Za-z][A-Za-z0-9]{1,24}\s+or\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\b([A-Za-z][A-Za-z0-9]{1,24})\s+was\s+wrong\b",
        )
        corrected_patterns = (
            r"\bis\s+named\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\b(?:her|his|their)\s+name\s+is\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bit\s+is\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bcorrect\s+name\s+is\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bcorrect\s+reference\s+(?:is|was)\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bperson\s+(?:is|was|now)\s+([A-Za-z][A-Za-z0-9]{1,24})\b",
            r"\bis\s+([A-Za-z][A-Za-z0-9]{1,24}),?\s+corrected\s+from\b",
            r"\bis\s+([A-Za-z][A-Za-z0-9]{1,24}),?\s+not\b",
        )

        for pattern in pair_patterns:
            for wrong, corrected in re.findall(pattern, content, flags=re.I):
                self._add_correction_term(wrong_terms, wrong)
                self._add_correction_term(corrected_terms, corrected)
        for pattern in wrong_patterns:
            for match in re.findall(pattern, content, flags=re.I):
                self._add_correction_term(wrong_terms, match)
        for pattern in corrected_patterns:
            for match in re.findall(pattern, content, flags=re.I):
                self._add_correction_term(corrected_terms, match)

        wrong_terms -= corrected_terms
        if not wrong_terms:
            return None
        return {"wrong": wrong_terms, "corrected": corrected_terms}

    def _add_correction_term(self, terms: set[str], value: Any) -> None:
        if isinstance(value, tuple):
            for item in value:
                self._add_correction_term(terms, item)
            return
        term = self._normalized_text(value)
        ignored_terms = {
            "actual",
            "another",
            "correct",
            "from",
            "name",
            "named",
            "not",
            "person",
            "prior",
            "real",
            "reference",
            "the",
            "wrong",
        }
        if len(term) < 2 or term in ignored_terms:
            return
        terms.add(term)

    def _is_stale_corrected_memory(
        self,
        memory: dict,
        correction: dict[str, set[str]],
    ) -> bool:
        if memory.get("active") is False:
            return False
        if not memory.get("id"):
            return False

        normalized = self._normalized_text(memory.get("content", ""))
        if not normalized:
            return False

        tokens = set(normalized.split())
        if not tokens.intersection(correction["wrong"]):
            return False
        corrected_terms = correction["corrected"]
        if corrected_terms and tokens.intersection(corrected_terms):
            return False
        return True

    def _normalized_text(self, text: Any) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))
