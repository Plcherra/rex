from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Optional, Protocol

from app.models.memory_discipline import (
    MemoryCandidateKind,
    MemoryDisciplineAction,
    MemoryDisciplineCandidate,
    MemoryDisciplineContext,
    MemoryDisciplineDecision,
    MemoryRelatedRecord,
)
from app.services.entity_normalization_service import EntityNormalizationService
from app.services.plan_intelligence_service import PlanIntelligenceService


DISCIPLINE_VERSION = 1
RELATED_RECORD_LIMIT = 5
RELATED_SCORE_THRESHOLD = 0.28
DUPLICATE_SCORE_THRESHOLD = 0.86


class MemoryDisciplineRepository(Protocol):
    async def list_long_term_memory(
        self,
        limit: int = 50,
        memory_type: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
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

    async def list_personal_rules(
        self,
        limit: int = 50,
        rule_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        pass

    async def list_plans(
        self,
        limit: int = 50,
        plan_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        pass

    async def list_plan_milestones(
        self,
        limit: int = 50,
        plan_id: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        pass

    async def list_commitments(
        self,
        limit: int = 50,
        commitment_type: Optional[str] = None,
        plan_id: Optional[str] = None,
        milestone_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        pass


class MemoryDisciplineService:
    """Shared pre-save policy for disciplined structured memory writes.

    Memory discipline policy:
    Before saving structured memory, Rex must check related active memory records
    and decide whether to update, merge, archive, create a milestone/task,
    create a new top-level plan, or ask for confirmation. Creating a new
    top-level plan is the last resort.
    """

    def __init__(
        self,
        memory_service: MemoryDisciplineRepository,
        *,
        scan_limit: int = 100,
    ) -> None:
        self.memory_service = memory_service
        self.scan_limit = scan_limit
        self.entity_normalization_service = EntityNormalizationService()
        self.plan_intelligence_service = PlanIntelligenceService()

    async def gather_context(
        self,
        candidate: MemoryDisciplineCandidate,
    ) -> MemoryDisciplineContext:
        candidate_text = candidate_record_text(candidate.payload)
        long_term_memories = await self._safe_list(
            "list_long_term_memory",
            active=True,
            limit=self.scan_limit,
        )
        entities = await self._safe_list(
            "list_entities",
            active=True,
            limit=self.scan_limit,
        )
        rules = await self._safe_list(
            "list_personal_rules",
            active=True,
            limit=self.scan_limit,
        )
        plans = await self._safe_list(
            "list_plans",
            active=True,
            limit=self.scan_limit,
        )
        milestones = await self._safe_list(
            "list_plan_milestones",
            active=True,
            limit=self.scan_limit,
        )
        commitments = await self._safe_list(
            "list_commitments",
            active=True,
            limit=self.scan_limit,
        )

        return MemoryDisciplineContext(
            candidate=candidate,
            active_entities=entities,
            active_plans=plans,
            active_milestones=milestones,
            active_commitments=commitments,
            active_rules=rules,
            active_long_term_memories=long_term_memories,
            related_entities=self._related_records(
                candidate,
                candidate_text,
                "entities",
                entities,
            ),
            related_plans=self._related_records(
                candidate,
                candidate_text,
                "plans",
                plans,
            ),
            related_milestones=self._related_records(
                candidate,
                candidate_text,
                "plan_milestones",
                milestones,
            ),
            related_commitments=self._related_records(
                candidate,
                candidate_text,
                "commitments",
                commitments,
            ),
            related_rules=self._related_records(
                candidate,
                candidate_text,
                "personal_rules",
                rules,
            ),
            related_long_term_memories=self._related_records(
                candidate,
                candidate_text,
                "long_term_memory",
                long_term_memories,
            ),
        )

    async def decide(
        self,
        candidate: MemoryDisciplineCandidate,
        context: Optional[MemoryDisciplineContext] = None,
    ) -> MemoryDisciplineDecision:
        context = context or await self.gather_context(candidate)
        candidate_text = candidate_record_text(candidate.payload)
        if not candidate_text:
            return MemoryDisciplineDecision(
                action=MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE,
                candidate_kind=candidate.kind,
                payload=candidate.payload,
                reason="Candidate has no useful searchable content.",
                confidence=0.95,
                metadata=self._decision_metadata(
                    MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE,
                    candidate,
                ),
            )

        same_kind_related = self._same_kind_related(candidate.kind, context)
        duplicate = same_kind_related[0] if same_kind_related else None
        if duplicate and duplicate.score >= DUPLICATE_SCORE_THRESHOLD:
            action = _update_action_for_kind(candidate.kind)
            if action:
                return MemoryDisciplineDecision(
                    action=action,
                    candidate_kind=candidate.kind,
                    payload=candidate.payload,
                    reason="Candidate strongly matches an active existing record.",
                    confidence=duplicate.score,
                    target_table=duplicate.table,
                    target_id=duplicate.id,
                    related_records=[duplicate],
                    metadata=self._decision_metadata(action, candidate),
                )

        if candidate.kind == MemoryCandidateKind.PLAN:
            plan_decision = self.plan_intelligence_service.classify_plan_candidate(
                candidate.payload,
                context,
            )
            if plan_decision.action != MemoryDisciplineAction.CREATE_PLAN:
                return self._decision_from_plan_intelligence(
                    candidate,
                    plan_decision,
                    context,
                )

        if candidate.kind == MemoryCandidateKind.PLAN_MILESTONE:
            milestone_decision = self._decide_milestone_candidate(candidate, context)
            if milestone_decision is not None:
                return milestone_decision

        action = _create_action_for_kind(candidate.kind)
        if action is None:
            return MemoryDisciplineDecision(
                action=MemoryDisciplineAction.ASK_CONFIRMATION,
                candidate_kind=candidate.kind,
                payload=candidate.payload,
                reason="Candidate kind needs a later phase-specific decision.",
                confidence=0.5,
                requires_confirmation=True,
                metadata=self._decision_metadata(
                    MemoryDisciplineAction.ASK_CONFIRMATION,
                    candidate,
                    requires_confirmation=True,
                ),
            )

        return MemoryDisciplineDecision(
            action=action,
            candidate_kind=candidate.kind,
            payload=candidate.payload,
            reason="No duplicate existing record passed the update threshold.",
            confidence=0.7,
            related_records=self._top_related_records(context),
            metadata=self._decision_metadata(action, candidate),
        )

    def _decide_milestone_candidate(
        self,
        candidate: MemoryDisciplineCandidate,
        context: MemoryDisciplineContext,
    ) -> MemoryDisciplineDecision | None:
        parent_plan = next(
            (
                plan
                for plan in context.active_plans
                if str(plan.get("id")) == str(candidate.payload.get("plan_id"))
            ),
            None,
        )
        if parent_plan is None:
            return None
        active_milestones = [
            milestone
            for milestone in context.active_milestones
            if str(milestone.get("plan_id")) == str(parent_plan.get("id"))
        ]
        classification = self.plan_intelligence_service.classify_milestone_candidate(
            candidate.payload,
            parent_plan,
            active_milestones,
        )
        metadata = {
            **self._decision_metadata(
                MemoryDisciplineAction.CREATE_MILESTONE,
                candidate,
            ),
            "milestone_classification": classification.model_dump(),
            "parent_plan_id": parent_plan.get("id"),
        }
        if classification.existing_milestone_id:
            return MemoryDisciplineDecision(
                action=MemoryDisciplineAction.UPDATE_MILESTONE,
                candidate_kind=MemoryCandidateKind.PLAN_MILESTONE,
                payload=candidate.payload,
                reason=classification.reason,
                confidence=classification.confidence,
                target_table="plan_milestones",
                target_id=classification.existing_milestone_id,
                related_records=self._top_related_records(context),
                metadata=metadata,
            )
        if classification.kind == "task":
            plan_decision = self.plan_intelligence_service.classify_plan_candidate(
                {
                    **candidate.payload,
                    "plan_type": parent_plan.get("plan_type"),
                },
                {
                    "active_plans": [parent_plan],
                    "active_milestones": active_milestones,
                },
            )
            if plan_decision.action == MemoryDisciplineAction.CREATE_COMMITMENT:
                return self._decision_from_plan_intelligence(candidate, plan_decision, context)
        if classification.kind in {"strategy_description_update", "entity_event"}:
            plan_decision = self.plan_intelligence_service.classify_plan_candidate(
                {
                    **candidate.payload,
                    "plan_type": parent_plan.get("plan_type"),
                },
                {
                    "active_plans": [parent_plan],
                    "active_milestones": active_milestones,
                },
            )
            if plan_decision.action in {
                MemoryDisciplineAction.UPDATE_PLAN,
                MemoryDisciplineAction.CREATE_ENTITY_EVENT,
            }:
                return self._decision_from_plan_intelligence(candidate, plan_decision, context)
        if classification.kind == "noisy_ignore":
            return MemoryDisciplineDecision(
                action=MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE,
                candidate_kind=MemoryCandidateKind.PLAN_MILESTONE,
                payload=candidate.payload,
                reason=classification.reason,
                confidence=classification.confidence,
                related_records=self._top_related_records(context),
                metadata=metadata,
            )
        return None

    async def apply_decision(self, decision: MemoryDisciplineDecision) -> dict:
        normalized_payload = await self._normalize_decision_payload(decision)
        payload = {
            **normalized_payload,
            "metadata": {
                **self._target_metadata(decision),
                **(normalized_payload.get("metadata") or {}),
                **decision.metadata,
            },
        }
        action = decision.action
        target_id = decision.target_id

        if action == MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE:
            return {"action": action.value, "applied": False, "reason": decision.reason}
        if action == MemoryDisciplineAction.ASK_CONFIRMATION:
            return {
                "action": action.value,
                "applied": False,
                "requires_confirmation": True,
                "reason": decision.reason,
                "related_records": [
                    record.model_dump() for record in decision.related_records
                ],
            }

        create_method = _create_method_for_action(action)
        if create_method:
            created = await getattr(self.memory_service, create_method)(payload)
            return {"action": action.value, "applied": True, "record": created}

        update_method = _update_method_for_action(action)
        if update_method and target_id:
            payload = self._merge_update_payload(decision, payload)
            updated = await getattr(self.memory_service, update_method)(
                target_id,
                **payload,
            )
            return {"action": action.value, "applied": True, "record": updated}

        archive_method = _archive_method_for_action(action)
        if archive_method and target_id:
            archived = await getattr(self.memory_service, archive_method)(target_id)
            return {"action": action.value, "applied": bool(archived)}

        raise ValueError(f"Unsupported memory discipline action: {action.value}")

    async def _normalize_decision_payload(
        self,
        decision: MemoryDisciplineDecision,
    ) -> dict[str, Any]:
        payload = dict(decision.payload)
        entities = await self._safe_list(
            "list_entities",
            active=True,
            limit=self.scan_limit,
        )
        if not entities:
            return payload
        if decision.candidate_kind == MemoryCandidateKind.ENTITY:
            return self.entity_normalization_service.normalize_candidate_entity(
                payload,
                entities,
            ).payload

        text_fields_by_kind: dict[MemoryCandidateKind, tuple[str, ...]] = {
            MemoryCandidateKind.PERSONAL_RULE: (
                "title",
                "rule_text",
                "trigger_keywords",
            ),
            MemoryCandidateKind.PLAN: ("title", "description", "desired_outcome"),
            MemoryCandidateKind.PLAN_MILESTONE: ("title", "description"),
            MemoryCandidateKind.COMMITMENT: ("title", "commitment_text"),
            MemoryCandidateKind.ENTITY_EVENT: ("title", "content"),
        }
        text_fields = text_fields_by_kind.get(decision.candidate_kind)
        if text_fields is None:
            return payload
        link_field = None
        if decision.candidate_kind == MemoryCandidateKind.PLAN:
            link_field = "primary_entity_id"
        elif decision.candidate_kind == MemoryCandidateKind.COMMITMENT:
            link_field = "entity_id"
        return self.entity_normalization_service.normalize_payload_references(
            payload,
            entities,
            text_fields=text_fields,
            link_field=link_field,
        ).payload

    def _target_metadata(self, decision: MemoryDisciplineDecision) -> dict[str, Any]:
        if not decision.target_id:
            return {}
        for related in decision.related_records:
            if related.id == decision.target_id:
                return dict(related.record.get("metadata") or {})
        return {}

    def _target_record(self, decision: MemoryDisciplineDecision) -> dict[str, Any]:
        if not decision.target_id:
            return {}
        for related in decision.related_records:
            if related.id == decision.target_id:
                return dict(related.record)
        return {}

    def _merge_update_payload(
        self,
        decision: MemoryDisciplineDecision,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if decision.action != MemoryDisciplineAction.UPDATE_ENTITY:
            return payload

        target = self._target_record(decision)
        if not target:
            return payload

        merged = dict(payload)
        candidate_display = str(payload.get("display_name") or "").strip()
        target_display = str(target.get("display_name") or "").strip()
        candidate_normalized = normalize_text(
            payload.get("normalized_name") or candidate_display
        )
        target_normalized = normalize_text(
            target.get("normalized_name") or target_display
        )

        if target_display and target_normalized:
            candidate_tokens = meaningful_tokens(candidate_normalized)
            target_tokens = meaningful_tokens(target_normalized)
            alias_values = {
                normalize_text(alias)
                for alias in target.get("aliases") or []
                if normalize_text(alias)
            }
            if (
                target_tokens
                and target_tokens <= candidate_tokens
                or candidate_normalized in alias_values
            ):
                merged["display_name"] = target_display
                merged["normalized_name"] = target.get("normalized_name") or target_normalized

        aliases = []
        for value in [
            *(target.get("aliases") or []),
            *(payload.get("aliases") or []),
        ]:
            if value and str(value) not in aliases:
                aliases.append(str(value))
        if (
            candidate_display
            and target_display
            and candidate_display.casefold() != target_display.casefold()
            and candidate_display not in aliases
        ):
            aliases.append(candidate_display)
        merged["aliases"] = aliases
        return merged

    async def _safe_list(self, method_name: str, **kwargs: Any) -> list[dict]:
        method = getattr(self.memory_service, method_name, None)
        if method is None:
            return []
        try:
            return await method(**kwargs)
        except TypeError:
            # Some test fakes use narrower signatures. Phase 1 should not make
            # chat/runtime brittle while the discipline layer is being wired in.
            return await method(limit=kwargs.get("limit", self.scan_limit))
        except Exception:
            return []

    def _related_records(
        self,
        candidate: MemoryDisciplineCandidate,
        candidate_text: str,
        table: str,
        records: list[dict],
    ) -> list[MemoryRelatedRecord]:
        related: list[MemoryRelatedRecord] = []
        for record in records:
            score, reason = record_similarity(candidate, candidate_text, table, record)
            if score < RELATED_SCORE_THRESHOLD:
                continue
            record_id = str(record.get("id") or "")
            if not record_id:
                continue
            related.append(
                MemoryRelatedRecord(
                    table=table,
                    id=record_id,
                    score=score,
                    title=record_title(record),
                    reason=reason,
                    record=record,
                )
            )
        return sorted(related, key=lambda item: item.score, reverse=True)[
            :RELATED_RECORD_LIMIT
        ]

    def _same_kind_related(
        self,
        kind: MemoryCandidateKind,
        context: MemoryDisciplineContext,
    ) -> list[MemoryRelatedRecord]:
        if kind == MemoryCandidateKind.LONG_TERM_MEMORY:
            return context.related_long_term_memories
        if kind == MemoryCandidateKind.ENTITY:
            return context.related_entities
        if kind == MemoryCandidateKind.PERSONAL_RULE:
            return context.related_rules
        if kind == MemoryCandidateKind.PLAN:
            return context.related_plans
        if kind == MemoryCandidateKind.PLAN_MILESTONE:
            return context.related_milestones
        if kind == MemoryCandidateKind.COMMITMENT:
            return context.related_commitments
        return []

    def _top_related_records(
        self,
        context: MemoryDisciplineContext,
    ) -> list[MemoryRelatedRecord]:
        records = [
            *context.related_entities,
            *context.related_plans,
            *context.related_milestones,
            *context.related_commitments,
            *context.related_rules,
            *context.related_long_term_memories,
        ]
        return sorted(records, key=lambda item: item.score, reverse=True)[
            :RELATED_RECORD_LIMIT
        ]

    def _decision_metadata(
        self,
        action: MemoryDisciplineAction,
        candidate: MemoryDisciplineCandidate,
        *,
        requires_confirmation: bool = False,
    ) -> dict[str, Any]:
        return {
            "discipline_version": DISCIPLINE_VERSION,
            "discipline_action": action.value,
            "discipline_reason": "phase_1_foundation",
            "merged_from_id": None,
            "archived_by_correction_id": None,
            "canonical_entity_id": None,
            "source_candidate_kind": candidate.kind.value,
            "requires_confirmation": requires_confirmation,
        }

    def _decision_from_plan_intelligence(
        self,
        candidate: MemoryDisciplineCandidate,
        plan_decision,
        context: MemoryDisciplineContext,
    ) -> MemoryDisciplineDecision:
        action_to_kind = {
            MemoryDisciplineAction.CREATE_ENTITY_EVENT: MemoryCandidateKind.ENTITY_EVENT,
            MemoryDisciplineAction.UPDATE_PLAN: MemoryCandidateKind.PLAN,
            MemoryDisciplineAction.CREATE_MILESTONE: MemoryCandidateKind.PLAN_MILESTONE,
            MemoryDisciplineAction.UPDATE_MILESTONE: MemoryCandidateKind.PLAN_MILESTONE,
            MemoryDisciplineAction.CREATE_COMMITMENT: MemoryCandidateKind.COMMITMENT,
            MemoryDisciplineAction.UPDATE_COMMITMENT: MemoryCandidateKind.COMMITMENT,
            MemoryDisciplineAction.ASK_CONFIRMATION: MemoryCandidateKind.PLAN,
            MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE: candidate.kind,
        }
        target_table = None
        target_id = plan_decision.target_milestone_id
        if plan_decision.action == MemoryDisciplineAction.CREATE_ENTITY_EVENT:
            target_table = "entity_events"
        elif plan_decision.action == MemoryDisciplineAction.UPDATE_PLAN:
            target_table = "plans"
            target_id = plan_decision.parent_plan_id
        elif plan_decision.action in {
            MemoryDisciplineAction.CREATE_MILESTONE,
            MemoryDisciplineAction.UPDATE_MILESTONE,
        }:
            target_table = "plan_milestones"
        elif plan_decision.action in {
            MemoryDisciplineAction.CREATE_COMMITMENT,
            MemoryDisciplineAction.UPDATE_COMMITMENT,
        }:
            target_table = "commitments"

        metadata = {
            **self._decision_metadata(
                plan_decision.action,
                candidate,
                requires_confirmation=plan_decision.requires_confirmation,
            ),
            **plan_decision.metadata,
        }
        if plan_decision.parent_plan_id:
            metadata["parent_plan_id"] = plan_decision.parent_plan_id
        if plan_decision.target_milestone_id:
            metadata["target_milestone_id"] = plan_decision.target_milestone_id

        related_records = self._top_related_records(context)
        return MemoryDisciplineDecision(
            action=plan_decision.action,
            candidate_kind=action_to_kind.get(plan_decision.action, candidate.kind),
            payload=plan_decision.payload,
            reason=plan_decision.reason,
            confidence=plan_decision.confidence,
            target_table=target_table,
            target_id=target_id,
            requires_confirmation=plan_decision.requires_confirmation,
            related_records=related_records,
            metadata=metadata,
        )


def record_similarity(
    candidate: MemoryDisciplineCandidate,
    candidate_text: str,
    table: str,
    record: dict[str, Any],
) -> tuple[float, str]:
    if _same_source(candidate, record):
        return 1.0, "same_source"

    record_text = record_text_for_table(table, record)
    if not candidate_text or not record_text:
        return 0.0, "empty_text"

    title_score = title_similarity_score(candidate.payload, record)
    token_score = token_overlap_score(candidate_text, record_text)
    sequence_score = normalized_similarity_score(candidate_text, record_text)
    alias_score = entity_alias_score(candidate_text, record)
    type_score = type_match_score(candidate, record)

    if token_score == 0 and alias_score == 0:
        if title_score >= 0.55:
            return title_score, "title_similarity"
        return 0.0, "no_overlap"

    score = max(
        title_score,
        alias_score,
        (token_score * 0.55) + (sequence_score * 0.35) + (type_score * 0.10),
    )
    reason = "text_similarity"
    if alias_score >= score and alias_score > 0:
        reason = "entity_alias"
    elif title_score >= score and title_score > 0:
        reason = "title_similarity"
    elif type_score > 0:
        reason = "type_and_text_similarity"
    return min(1.0, score), reason


def candidate_record_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for field_name in (
        "title",
        "display_name",
        "normalized_name",
        "content",
        "summary",
        "description",
        "desired_outcome",
        "relationship",
        "rule_text",
        "commitment_text",
        "plan_type",
        "entity_type",
        "rule_type",
        "commitment_type",
    ):
        value = payload.get(field_name)
        if value:
            parts.append(str(value))
    for value in payload.get("aliases") or []:
        parts.append(str(value))
    for value in payload.get("trigger_keywords") or []:
        parts.append(str(value))
    return normalize_text(" ".join(parts))


def record_text_for_table(table: str, record: dict[str, Any]) -> str:
    return candidate_record_text(record)


def title_similarity_score(candidate_payload: dict[str, Any], record: dict[str, Any]) -> float:
    candidate_title = normalize_text(
        candidate_payload.get("title")
        or candidate_payload.get("display_name")
        or candidate_payload.get("content")
        or ""
    )
    record_title_text = normalize_text(
        record.get("title") or record.get("display_name") or record.get("content") or ""
    )
    if not candidate_title or not record_title_text:
        return 0.0
    return normalized_similarity_score(candidate_title, record_title_text)


def token_overlap_score(left: str, right: str) -> float:
    left_tokens = meaningful_tokens(left)
    right_tokens = meaningful_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return overlap / min(len(left_tokens), len(right_tokens))


def normalized_similarity_score(left: str, right: str) -> float:
    left = normalize_text(left)
    right = normalize_text(right)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def entity_alias_score(candidate_text: str, record: dict[str, Any]) -> float:
    aliases = [
        normalize_text(alias)
        for alias in record.get("aliases") or []
        if normalize_text(alias)
    ]
    normalized_candidate = normalize_text(candidate_text)
    if not aliases or not normalized_candidate:
        return 0.0
    candidate_tokens = meaningful_tokens(normalized_candidate)
    for alias in aliases:
        if alias == normalized_candidate:
            return 1.0
        if alias in normalized_candidate:
            return 0.92
        alias_tokens = meaningful_tokens(alias)
        if alias_tokens and alias_tokens <= candidate_tokens:
            return 0.88
    return 0.0


def type_match_score(candidate: MemoryDisciplineCandidate, record: dict[str, Any]) -> float:
    type_fields = (
        "entity_type",
        "plan_type",
        "rule_type",
        "commitment_type",
        "milestone_type",
        "memory_type",
    )
    for field_name in type_fields:
        candidate_value = candidate.payload.get(field_name)
        record_value = record.get(field_name)
        if candidate_value and record_value and candidate_value == record_value:
            return 1.0
    return 0.0


def normalize_text(value: Any) -> str:
    text = re.sub(r"[^a-z0-9$]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def meaningful_tokens(value: Any) -> set[str]:
    tokens = set(normalize_text(value).split())
    return {
        token
        for token in tokens
        if len(token) > 1
        and token
        not in {
            "a",
            "an",
            "and",
            "for",
            "in",
            "of",
            "on",
            "or",
            "the",
            "to",
            "with",
        }
    }


def record_title(record: dict[str, Any]) -> Optional[str]:
    for field_name in ("title", "display_name", "content", "rule_text"):
        value = record.get(field_name)
        if value:
            return str(value)
    return None


def _same_source(candidate: MemoryDisciplineCandidate, record: dict[str, Any]) -> bool:
    for field_name in (
        "source_memory_id",
        "source_message_id",
        "source_conversation_id",
    ):
        candidate_value = getattr(candidate, field_name)
        record_value = record.get(field_name)
        if candidate_value and record_value and str(candidate_value) == str(record_value):
            return True
    return False


def _create_action_for_kind(
    kind: MemoryCandidateKind,
) -> MemoryDisciplineAction | None:
    return {
        MemoryCandidateKind.ENTITY: MemoryDisciplineAction.CREATE_ENTITY,
        MemoryCandidateKind.ENTITY_EVENT: MemoryDisciplineAction.CREATE_ENTITY_EVENT,
        MemoryCandidateKind.PERSONAL_RULE: MemoryDisciplineAction.CREATE_RULE,
        MemoryCandidateKind.PLAN: MemoryDisciplineAction.CREATE_PLAN,
        MemoryCandidateKind.PLAN_MILESTONE: MemoryDisciplineAction.CREATE_MILESTONE,
        MemoryCandidateKind.COMMITMENT: MemoryDisciplineAction.CREATE_COMMITMENT,
    }.get(kind)


def _update_action_for_kind(
    kind: MemoryCandidateKind,
) -> MemoryDisciplineAction | None:
    return {
        MemoryCandidateKind.ENTITY: MemoryDisciplineAction.UPDATE_ENTITY,
        MemoryCandidateKind.PERSONAL_RULE: MemoryDisciplineAction.UPDATE_RULE,
        MemoryCandidateKind.PLAN: MemoryDisciplineAction.UPDATE_PLAN,
        MemoryCandidateKind.PLAN_MILESTONE: MemoryDisciplineAction.UPDATE_MILESTONE,
        MemoryCandidateKind.COMMITMENT: MemoryDisciplineAction.UPDATE_COMMITMENT,
    }.get(kind)


def _create_method_for_action(action: MemoryDisciplineAction) -> str | None:
    return {
        MemoryDisciplineAction.CREATE_ENTITY: "create_entity",
        MemoryDisciplineAction.CREATE_ENTITY_EVENT: "create_entity_event",
        MemoryDisciplineAction.CREATE_PLAN: "create_plan",
        MemoryDisciplineAction.CREATE_MILESTONE: "create_plan_milestone",
        MemoryDisciplineAction.CREATE_COMMITMENT: "create_commitment",
        MemoryDisciplineAction.CREATE_RULE: "create_personal_rule",
    }.get(action)


def _update_method_for_action(action: MemoryDisciplineAction) -> str | None:
    return {
        MemoryDisciplineAction.UPDATE_ENTITY: "update_entity",
        MemoryDisciplineAction.UPDATE_PLAN: "update_plan",
        MemoryDisciplineAction.UPDATE_MILESTONE: "update_plan_milestone",
        MemoryDisciplineAction.UPDATE_COMMITMENT: "update_commitment",
        MemoryDisciplineAction.UPDATE_RULE: "update_personal_rule",
    }.get(action)


def _archive_method_for_action(action: MemoryDisciplineAction) -> str | None:
    return {
        MemoryDisciplineAction.ARCHIVE_ENTITY: "deactivate_entity",
        MemoryDisciplineAction.ARCHIVE_PLAN: "deactivate_plan",
        MemoryDisciplineAction.ARCHIVE_RULE: "deactivate_personal_rule",
    }.get(action)
