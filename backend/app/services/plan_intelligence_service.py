from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.memory_discipline import MemoryDisciplineAction


PLAN_INTELLIGENCE_VERSION = 1
PARENT_PLAN_THRESHOLD = 0.28
RELATED_MILESTONE_THRESHOLD = 0.78
TOP_LEVEL_MINIMUM_SPECIFICITY = 0.42
MAX_AUTO_TOP_LEVEL_PLANS = 5


class PlanIntelligenceDecision(BaseModel):
    action: MemoryDisciplineAction
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str
    confidence: float = Field(default=0.75, ge=0, le=1)
    parent_plan_id: Optional[str] = None
    target_milestone_id: Optional[str] = None
    requires_confirmation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanIntelligenceService:
    """Routes plan-like candidates into a stable hierarchy.

    The default preference is:
    top-level plan -> milestone -> commitment/task
    Creating another active top-level plan is only allowed when no existing plan
    is a reasonable parent and the candidate is durable enough to stand alone.
    """

    def classify_plan_candidate(
        self,
        candidate: dict[str, Any],
        context: Any,
    ) -> PlanIntelligenceDecision:
        active_plans = _context_records(context, "active_plans")
        if not active_plans:
            active_plans = _records_from_related(context, "related_plans")
        active_milestones = _context_records(context, "active_milestones")
        if not active_milestones:
            active_milestones = _records_from_related(context, "related_milestones")

        parent_plan, parent_score = self.find_best_parent_plan(
            candidate,
            active_plans,
        )
        if parent_plan:
            related_milestone, milestone_score = self.find_related_milestone(
                candidate,
                [
                    milestone
                    for milestone in active_milestones
                    if milestone.get("plan_id") == parent_plan.get("id")
                ],
            )
            if related_milestone:
                return PlanIntelligenceDecision(
                    action=MemoryDisciplineAction.UPDATE_MILESTONE,
                    payload=self.build_milestone_from_plan_candidate(
                        candidate,
                        parent_plan,
                        existing_milestone=related_milestone,
                    ),
                    reason="Plan candidate updates an existing milestone under an active parent plan.",
                    confidence=milestone_score,
                    parent_plan_id=str(parent_plan.get("id")),
                    target_milestone_id=str(related_milestone.get("id")),
                    metadata=_route_metadata("update_related_milestone", parent_score),
                )

            if _is_small_step(candidate):
                milestone = _best_milestone_for_commitment(
                    candidate,
                    [
                        item
                        for item in active_milestones
                        if item.get("plan_id") == parent_plan.get("id")
                    ],
                )
                payload = self.build_commitment_from_small_step(
                    candidate,
                    parent_plan,
                    milestone=milestone,
                )
                return PlanIntelligenceDecision(
                    action=MemoryDisciplineAction.CREATE_COMMITMENT,
                    payload=payload,
                    reason="Plan candidate is a concrete next action, so it belongs as a commitment under the active parent plan.",
                    confidence=max(parent_score, 0.76),
                    parent_plan_id=str(parent_plan.get("id")),
                    target_milestone_id=str(milestone.get("id"))
                    if milestone
                    else None,
                    metadata=_route_metadata("small_step_to_commitment", parent_score),
                )

            payload = self.build_milestone_from_plan_candidate(candidate, parent_plan)
            return PlanIntelligenceDecision(
                action=MemoryDisciplineAction.CREATE_MILESTONE,
                payload=payload,
                reason="Plan candidate belongs under an existing active top-level plan.",
                confidence=max(parent_score, 0.74),
                parent_plan_id=str(parent_plan.get("id")),
                metadata=_route_metadata("related_plan_to_milestone", parent_score),
            )

        if self.should_create_top_level_plan(candidate, context):
            return PlanIntelligenceDecision(
                action=MemoryDisciplineAction.CREATE_PLAN,
                payload=candidate,
                reason="Candidate is durable and distinct enough to become a top-level plan.",
                confidence=0.72,
                metadata=_route_metadata("new_top_level_plan", 0),
            )

        return PlanIntelligenceDecision(
            action=MemoryDisciplineAction.ASK_CONFIRMATION,
            payload=candidate,
            reason="Candidate is plan-like but not specific or durable enough to safely create as a top-level plan.",
            confidence=0.56,
            requires_confirmation=True,
            metadata=_route_metadata("ambiguous_plan_candidate", 0),
        )

    def find_best_parent_plan(
        self,
        candidate: dict[str, Any],
        active_plans: list[dict[str, Any]],
    ) -> tuple[Optional[dict[str, Any]], float]:
        scored = [
            (plan, _parent_plan_score(candidate, plan))
            for plan in active_plans
            if plan.get("active", True)
            and str(plan.get("status") or "active") in {"active", "in_progress"}
        ]
        if not scored:
            return None, 0
        best_plan, best_score = max(scored, key=lambda item: item[1])
        if best_score < PARENT_PLAN_THRESHOLD:
            return None, best_score
        return best_plan, best_score

    def find_related_milestone(
        self,
        candidate: dict[str, Any],
        active_milestones: list[dict[str, Any]],
    ) -> tuple[Optional[dict[str, Any]], float]:
        scored = [
            (milestone, _similarity(_candidate_text(candidate), _record_text(milestone)))
            for milestone in active_milestones
            if milestone.get("active", True)
            and str(milestone.get("status") or "open") in {"open", "in_progress"}
        ]
        if not scored:
            return None, 0
        best_milestone, best_score = max(scored, key=lambda item: item[1])
        if best_score < RELATED_MILESTONE_THRESHOLD:
            return None, best_score
        return best_milestone, best_score

    def should_create_top_level_plan(
        self,
        candidate: dict[str, Any],
        context: Any,
    ) -> bool:
        active_plans = _context_records(context, "active_plans")
        parent_plan, _ = self.find_best_parent_plan(candidate, active_plans)
        if parent_plan:
            return False
        if not active_plans and _has_standalone_anchor(candidate):
            return _specificity_score(candidate, small_step_penalty=False) >= 0.38
        if len(active_plans) >= MAX_AUTO_TOP_LEVEL_PLANS:
            return False
        if _is_small_step(candidate):
            return False
        return _specificity_score(candidate) >= TOP_LEVEL_MINIMUM_SPECIFICITY

    def build_milestone_from_plan_candidate(
        self,
        candidate: dict[str, Any],
        parent_plan: dict[str, Any],
        *,
        existing_milestone: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        metadata = {
            **(existing_milestone.get("metadata") if existing_milestone else {}),
            **(candidate.get("metadata") or {}),
            "plan_intelligence_version": PLAN_INTELLIGENCE_VERSION,
            "routed_from": "plan_candidate",
            "parent_plan_id": parent_plan.get("id"),
            "parent_plan_title": parent_plan.get("title"),
        }
        return _drop_none(
            {
                "plan_id": parent_plan.get("id"),
                "title": _clean(candidate.get("title")) or "Plan milestone",
                "description": _join_parts(
                    candidate.get("description"),
                    candidate.get("desired_outcome"),
                ),
                "milestone_type": _milestone_type(candidate),
                "target_date": candidate.get("target_date"),
                "source_conversation_id": candidate.get("source_conversation_id"),
                "source_message_id": candidate.get("source_message_id"),
                "source_memory_id": candidate.get("source_memory_id"),
                "priority": candidate.get("priority", parent_plan.get("priority", 3)),
                "status": "open",
                "active": True,
                "metadata": metadata,
            }
        )

    def build_commitment_from_small_step(
        self,
        candidate: dict[str, Any],
        parent_plan: dict[str, Any],
        milestone: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        metadata = {
            **(candidate.get("metadata") or {}),
            "plan_intelligence_version": PLAN_INTELLIGENCE_VERSION,
            "routed_from": "plan_candidate",
            "parent_plan_id": parent_plan.get("id"),
            "parent_plan_title": parent_plan.get("title"),
        }
        if milestone:
            metadata["parent_milestone_title"] = milestone.get("title")
        return _drop_none(
            {
                "commitment_type": _commitment_type(candidate, parent_plan),
                "title": _clean(candidate.get("title")) or "Plan next step",
                "commitment_text": _join_parts(
                    candidate.get("description"),
                    candidate.get("desired_outcome"),
                )
                or _clean(candidate.get("title"))
                or "Complete the next step.",
                "plan_id": parent_plan.get("id"),
                "milestone_id": milestone.get("id") if milestone else None,
                "entity_id": candidate.get("primary_entity_id"),
                "source_conversation_id": candidate.get("source_conversation_id"),
                "source_message_id": candidate.get("source_message_id"),
                "source_memory_id": candidate.get("source_memory_id"),
                "priority": candidate.get("priority", parent_plan.get("priority", 3)),
                "status": "open",
                "active": True,
                "due_at": candidate.get("target_date"),
                "metadata": metadata,
            }
        )


def _parent_plan_score(candidate: dict[str, Any], plan: dict[str, Any]) -> float:
    candidate_text = _candidate_text(candidate)
    plan_text = _record_text(plan)
    score = _similarity(candidate_text, plan_text)
    candidate_type = str(candidate.get("plan_type") or "").lower()
    plan_type = str(plan.get("plan_type") or "").lower()
    if candidate_type and candidate_type == plan_type:
        score += 0.08
    elif candidate_type and plan_type and not _compatible_plan_types(
        candidate_type,
        plan_type,
    ):
        score -= 0.18
    if candidate.get("primary_entity_id") and candidate.get("primary_entity_id") == plan.get(
        "primary_entity_id"
    ):
        score += 0.22
    score += _domain_bridge_score(candidate_text, plan_text)
    return min(score, 1.0)


def _compatible_plan_types(candidate_type: str, plan_type: str) -> bool:
    compatible_groups = [
        {"career", "creative", "finance", "other"},
        {"finance", "immigration", "personal"},
        {"immigration", "housing", "personal"},
    ]
    return any({candidate_type, plan_type} <= group for group in compatible_groups)


def _domain_bridge_score(candidate_text: str, plan_text: str) -> float:
    candidate_tokens = _tokens(candidate_text)
    plan_tokens = _tokens(plan_text)
    boost = 0.0
    if candidate_tokens & {
        "income",
        "revenue",
        "savings",
        "client",
        "clients",
        "freelance",
        "paycheck",
    }:
        if plan_tokens & {
            "europe",
            "relocate",
            "relocation",
            "move",
            "freedom",
            "income",
            "location",
            "independent",
        }:
            boost += 0.25
    if candidate_tokens & {
        "abroad",
        "citizenship",
        "digital",
        "estonia",
        "europe",
        "greece",
        "immigration",
        "italian",
        "italy",
        "nomad",
        "portugal",
        "relocate",
        "relocation",
        "residency",
        "usa",
        "visa",
    }:
        if plan_tokens & {
            "abroad",
            "citizenship",
            "europe",
            "greece",
            "immigration",
            "italy",
            "move",
            "relocate",
            "relocation",
            "usa",
        }:
            boost += 0.42
    if candidate_tokens & {
        "app",
        "apps",
        "build",
        "clarity",
        "development",
        "echodesk",
        "flowforce",
        "launch",
        "mvp",
        "rex",
        "ship",
    }:
        if plan_tokens & {
            "app",
            "apps",
            "build",
            "development",
            "echodesk",
            "flowforce",
            "launch",
            "mvp",
            "project",
            "rex",
            "roadmap",
            "ship",
        }:
            boost += 0.34
    if candidate_tokens & {"date", "dinner", "restaurant", "monday", "text", "melissa"}:
        if plan_tokens & {"date", "dating", "dinner", "relationship", "melissa"}:
            boost += 0.25
    return boost


def _best_milestone_for_commitment(
    candidate: dict[str, Any],
    active_milestones: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not active_milestones:
        return None
    candidate_text = _candidate_text(candidate)
    best_milestone, best_score = max(
        (
            (milestone, _similarity(candidate_text, _record_text(milestone)))
            for milestone in active_milestones
            if milestone.get("active", True)
            and str(milestone.get("status") or "open") in {"open", "in_progress"}
        ),
        key=lambda item: item[1],
        default=(None, 0),
    )
    if best_score < 0.25:
        return None
    return best_milestone


def _is_small_step(candidate: dict[str, Any]) -> bool:
    text = _candidate_text(candidate)
    tokens = _tokens(text)
    if tokens & {
        "confirm",
        "text",
        "message",
        "call",
        "book",
        "schedule",
        "send",
        "ask",
        "pay",
        "transfer",
        "email",
        "choose",
        "pick",
    }:
        return True
    if str(candidate.get("target_date") or "").strip():
        return True
    return False


def _specificity_score(
    candidate: dict[str, Any],
    *,
    small_step_penalty: bool = True,
) -> float:
    text = _candidate_text(candidate)
    tokens = _tokens(text)
    score = min(len(tokens) / 14, 0.55)
    if _clean(candidate.get("desired_outcome")):
        score += 0.18
    if _clean(candidate.get("description")):
        score += 0.16
    if str(candidate.get("plan_type") or "").strip():
        score += 0.08
    if small_step_penalty and _is_small_step(candidate):
        score -= 0.22
    return max(0.0, min(score, 1.0))


def _has_standalone_anchor(candidate: dict[str, Any]) -> bool:
    plan_type = str(candidate.get("plan_type") or "").strip().lower()
    if plan_type not in {
        "career",
        "creative",
        "dating",
        "finance",
        "health",
        "housing",
        "immigration",
        "personal",
    }:
        return False
    return bool(
        _clean(candidate.get("description"))
        or _clean(candidate.get("desired_outcome"))
        or _clean(candidate.get("entity_name"))
        or _clean(candidate.get("primary_entity_id"))
    )


def _similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = SequenceMatcher(None, left, right).ratio()
    return (overlap * 0.68) + (sequence * 0.32)


def _candidate_text(candidate: dict[str, Any]) -> str:
    return _join_parts(
        candidate.get("plan_type"),
        candidate.get("title"),
        candidate.get("description"),
        candidate.get("desired_outcome"),
        candidate.get("entity_name"),
    ).lower()


def _record_text(record: dict[str, Any]) -> str:
    return _join_parts(
        record.get("plan_type"),
        record.get("title"),
        record.get("description"),
        record.get("desired_outcome"),
        record.get("relationship"),
        record.get("summary"),
    ).lower()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value).lower())
        if len(token) > 2 and token not in _STOP_WORDS
    }


def _context_records(context: Any, field: str) -> list[dict[str, Any]]:
    if isinstance(context, dict):
        return list(context.get(field) or [])
    return list(getattr(context, field, []) or [])


def _records_from_related(context: Any, field: str) -> list[dict[str, Any]]:
    related = _context_records(context, field)
    records = []
    for item in related:
        if isinstance(item, dict):
            records.append(item.get("record") or item)
        else:
            records.append(getattr(item, "record", {}) or {})
    return records


def _route_metadata(reason: str, score: float) -> dict[str, Any]:
    return {
        "plan_intelligence_version": PLAN_INTELLIGENCE_VERSION,
        "plan_intelligence_reason": reason,
        "parent_plan_score": round(score, 4),
    }


def _milestone_type(candidate: dict[str, Any]) -> str:
    if str(candidate.get("target_date") or "").strip():
        return "deadline"
    if _is_small_step(candidate):
        return "task"
    return "goal"


def _commitment_type(candidate: dict[str, Any], parent_plan: dict[str, Any]) -> str:
    plan_type = str(candidate.get("plan_type") or parent_plan.get("plan_type") or "").lower()
    if plan_type in {"health", "immigration", "dating"}:
        return {"dating": "relationship"}.get(plan_type, plan_type)
    if plan_type in {"career", "creative"}:
        return "work"
    if plan_type == "finance":
        return "money"
    return "task"


def _join_parts(*parts: Any) -> str:
    return " ".join(_clean(part) for part in parts if _clean(part))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_clean(item) for item in value)
    return re.sub(r"\s+", " ", str(value)).strip()


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


_STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "next",
    "not",
    "out",
    "that",
    "the",
    "this",
    "user",
    "with",
    "year",
}
