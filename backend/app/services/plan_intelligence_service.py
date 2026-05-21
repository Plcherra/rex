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
DESCRIPTION_MIN_TOKENS = 8


class PlanIntelligenceDecision(BaseModel):
    action: MemoryDisciplineAction
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str
    confidence: float = Field(default=0.75, ge=0, le=1)
    parent_plan_id: Optional[str] = None
    target_milestone_id: Optional[str] = None
    requires_confirmation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanDescriptionQuality(BaseModel):
    passed: bool
    reason: str
    score: float = Field(ge=0, le=1)


class MilestoneClassification(BaseModel):
    kind: str
    reason: str
    confidence: float = Field(default=0.75, ge=0, le=1)
    existing_milestone_id: Optional[str] = None


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

        if _is_first_million_exploration(_candidate_text(candidate)):
            return PlanIntelligenceDecision(
                action=MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE,
                payload=candidate,
                reason="Exploratory first-million discussion is not an active plan or milestone.",
                confidence=0.86,
                metadata=_route_metadata("first_million_exploration_ignored", 0),
            )

        parent_plan, parent_score = self.find_best_parent_plan(
            candidate,
            active_plans,
        )
        if parent_plan:
            milestones_for_parent = [
                milestone
                for milestone in active_milestones
                if milestone.get("plan_id") == parent_plan.get("id")
            ]
            milestone_classification = self.classify_milestone_candidate(
                candidate,
                parent_plan,
                milestones_for_parent,
            )
            related_milestone, milestone_score = self.find_related_milestone(
                candidate,
                milestones_for_parent,
            )
            if milestone_classification.existing_milestone_id:
                related_milestone = next(
                    (
                        milestone
                        for milestone in milestones_for_parent
                        if str(milestone.get("id"))
                        == milestone_classification.existing_milestone_id
                    ),
                    related_milestone,
                )
                milestone_score = milestone_classification.confidence
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
                    metadata={
                        **_route_metadata("update_related_milestone", parent_score),
                        "milestone_classification": milestone_classification.model_dump(),
                    },
                )

            if milestone_classification.kind == "task" or _is_small_step(candidate):
                milestone = _best_milestone_for_commitment(
                    candidate,
                    milestones_for_parent,
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
                    metadata={
                        **_route_metadata("small_step_to_commitment", parent_score),
                        "milestone_classification": milestone_classification.model_dump(),
                    },
                )

            if milestone_classification.kind in {
                "strategy_description_update",
                "entity_event",
            }:
                if milestone_classification.kind == "entity_event" and (
                    candidate.get("primary_entity_id")
                    or candidate.get("entity_id")
                    or candidate.get("entity_name")
                ):
                    return PlanIntelligenceDecision(
                        action=MemoryDisciplineAction.CREATE_ENTITY_EVENT,
                        payload=self.build_entity_event_from_plan_candidate(
                            candidate,
                            parent_plan,
                        ),
                        reason="Plan candidate is historical relationship context, so it belongs as an entity event.",
                        confidence=max(parent_score, milestone_classification.confidence),
                        parent_plan_id=str(parent_plan.get("id")),
                        metadata={
                            **_route_metadata("plan_detail_to_entity_event", parent_score),
                            "milestone_classification": milestone_classification.model_dump(),
                        },
                    )
                return PlanIntelligenceDecision(
                    action=MemoryDisciplineAction.UPDATE_PLAN,
                    payload=self.build_plan_description_update(candidate, parent_plan),
                    reason="Plan candidate is strategy/context, so it should enrich the parent plan description instead of becoming another milestone.",
                    confidence=max(parent_score, milestone_classification.confidence),
                    parent_plan_id=str(parent_plan.get("id")),
                    metadata={
                        **_route_metadata("plan_detail_to_description", parent_score),
                        "milestone_classification": milestone_classification.model_dump(),
                    },
                )

            if milestone_classification.kind == "noisy_ignore":
                return PlanIntelligenceDecision(
                    action=MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE,
                    payload=candidate,
                    reason=milestone_classification.reason,
                    confidence=milestone_classification.confidence,
                    parent_plan_id=str(parent_plan.get("id")),
                    metadata={
                        **_route_metadata("noisy_plan_detail_ignored", parent_score),
                        "milestone_classification": milestone_classification.model_dump(),
                    },
                )

            payload = self.build_milestone_from_plan_candidate(candidate, parent_plan)
            return PlanIntelligenceDecision(
                action=MemoryDisciplineAction.CREATE_MILESTONE,
                payload=payload,
                reason="Plan candidate is a badge-like achievement under an existing active top-level plan.",
                confidence=max(parent_score, 0.74),
                parent_plan_id=str(parent_plan.get("id")),
                metadata={
                    **_route_metadata("related_plan_to_milestone", parent_score),
                    "milestone_classification": milestone_classification.model_dump(),
                },
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
            return (
                self.validate_plan_description(candidate).passed
                and _specificity_score(candidate, small_step_penalty=False) >= 0.38
            )
        if len(active_plans) >= MAX_AUTO_TOP_LEVEL_PLANS:
            return False
        if _is_small_step(candidate):
            return False
        if not self.validate_plan_description(candidate).passed:
            return False
        return _specificity_score(candidate) >= TOP_LEVEL_MINIMUM_SPECIFICITY

    def validate_plan_description(self, candidate: dict[str, Any]) -> PlanDescriptionQuality:
        description = _clean(candidate.get("description"))
        desired = _clean(candidate.get("desired_outcome"))
        combined = _join_parts(description, desired)
        tokens = _tokens(combined)
        score = min(len(tokens) / DESCRIPTION_MIN_TOKENS, 0.65)
        if _has_strategy_signal(combined):
            score += 0.16
        if _has_success_signal(combined):
            score += 0.16
        if _has_timeline_or_target(combined):
            score += 0.12
        score = min(score, 1.0)
        if len(tokens) < DESCRIPTION_MIN_TOKENS:
            return PlanDescriptionQuality(
                passed=False,
                reason="Top-level plan description is too thin.",
                score=score,
            )
        if not (_has_strategy_signal(combined) or _has_success_signal(combined)):
            return PlanDescriptionQuality(
                passed=False,
                reason="Top-level plan description needs strategy or success criteria.",
                score=score,
            )
        return PlanDescriptionQuality(
            passed=True,
            reason="Top-level plan description is specific enough.",
            score=score,
        )

    def classify_milestone_candidate(
        self,
        candidate: dict[str, Any],
        parent_plan: dict[str, Any],
        active_milestones: list[dict[str, Any]],
    ) -> MilestoneClassification:
        candidate_text = _candidate_text(candidate)
        title = _clean(candidate.get("title"))
        parent_title = _clean(parent_plan.get("title"))

        existing = _duplicate_milestone(candidate, active_milestones)
        if existing:
            return MilestoneClassification(
                kind="duplicate",
                reason="Candidate duplicates an existing open milestone.",
                confidence=0.94,
                existing_milestone_id=str(existing.get("id")),
            )

        if _titles_equivalent(title, parent_title):
            return MilestoneClassification(
                kind="strategy_description_update",
                reason="Candidate repeats the parent plan title.",
                confidence=0.9,
            )

        if _is_first_million_exploration(candidate_text):
            return MilestoneClassification(
                kind="noisy_ignore",
                reason="Exploratory first-million discussion is not an active milestone.",
                confidence=0.86,
            )

        if _is_dating_logistics(candidate, parent_plan):
            return MilestoneClassification(
                kind="task",
                reason="Dating logistics should be one actionable task, not repeated milestones.",
                confidence=0.82,
            )

        if _is_small_step(candidate):
            return MilestoneClassification(
                kind="task",
                reason="Candidate is a concrete next action.",
                confidence=0.84,
            )

        if _is_historical_context(candidate_text):
            return MilestoneClassification(
                kind="entity_event",
                reason="Candidate is historical context better stored as an entity event or plan note.",
                confidence=0.76,
            )

        if _is_badge_like_achievement(candidate):
            return MilestoneClassification(
                kind="achievement",
                reason="Candidate is a measurable or completable achievement checkpoint.",
                confidence=0.82,
            )

        return MilestoneClassification(
            kind="strategy_description_update",
            reason="Candidate is broad strategy/context rather than a badge-like milestone.",
            confidence=0.74,
        )

    def build_milestone_from_plan_candidate(
        self,
        candidate: dict[str, Any],
        parent_plan: dict[str, Any],
        *,
        existing_milestone: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        metadata = {
            **((existing_milestone.get("metadata") or {}) if existing_milestone else {}),
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

    def build_plan_description_update(
        self,
        candidate: dict[str, Any],
        parent_plan: dict[str, Any],
    ) -> dict[str, Any]:
        candidate_detail = _join_parts(
            candidate.get("title"),
            candidate.get("description"),
            candidate.get("desired_outcome"),
        )
        description = _append_unique_detail(
            _clean(parent_plan.get("description")),
            candidate_detail,
        )
        return _drop_none(
            {
                "title": parent_plan.get("title"),
                "description": description,
                "desired_outcome": parent_plan.get("desired_outcome"),
                "priority": parent_plan.get("priority", candidate.get("priority", 3)),
                "metadata": {
                    **(parent_plan.get("metadata") or {}),
                    "plan_intelligence_version": PLAN_INTELLIGENCE_VERSION,
                    "routed_from": "plan_candidate",
                    "merged_plan_detail": True,
                    "merged_source_title": candidate.get("title"),
                },
            }
        )

    def build_entity_event_from_plan_candidate(
        self,
        candidate: dict[str, Any],
        parent_plan: dict[str, Any],
    ) -> dict[str, Any]:
        title = _clean(candidate.get("title")) or "Plan context"
        content = _join_parts(
            candidate.get("description"),
            candidate.get("desired_outcome"),
        ) or title
        return _drop_none(
            {
                "entity_id": candidate.get("entity_id")
                or candidate.get("primary_entity_id")
                or parent_plan.get("primary_entity_id"),
                "entity_name": candidate.get("entity_name"),
                "event_type": "relationship_update"
                if _is_dating_logistics(candidate, parent_plan)
                else "note",
                "title": title,
                "content": content,
                "source_conversation_id": candidate.get("source_conversation_id"),
                "source_message_id": candidate.get("source_message_id"),
                "source_memory_id": candidate.get("source_memory_id"),
                "importance": candidate.get("priority", parent_plan.get("priority", 3)),
                "active": True,
                "metadata": {
                    **(candidate.get("metadata") or {}),
                    "plan_intelligence_version": PLAN_INTELLIGENCE_VERSION,
                    "routed_from": "plan_candidate",
                    "parent_plan_id": parent_plan.get("id"),
                    "parent_plan_title": parent_plan.get("title"),
                },
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


def _duplicate_milestone(
    candidate: dict[str, Any],
    active_milestones: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    title = _clean(candidate.get("title"))
    candidate_text = _candidate_text(candidate)
    candidate_money = _money_targets(candidate_text)
    for milestone in active_milestones:
        if not milestone.get("active", True):
            continue
        if str(milestone.get("status") or "open") not in {"open", "in_progress"}:
            continue
        milestone_title = _clean(milestone.get("title"))
        milestone_text = _record_text(milestone)
        if _titles_equivalent(title, milestone_title):
            return milestone
        if _similarity(candidate_text, milestone_text) >= 0.82:
            return milestone
        if candidate_money and candidate_money == _money_targets(milestone_text):
            if _tokens(candidate_text) & {
                "income",
                "monthly",
                "month",
                "revenue",
                "target",
            }:
                return milestone
    return None


def _titles_equivalent(left: str, right: str) -> bool:
    left_key = _normalize_title(left)
    right_key = _normalize_title(right)
    if not left_key or not right_key:
        return False
    return left_key == right_key or _similarity(left_key, right_key) >= 0.9


def _normalize_title(value: str) -> str:
    return " ".join(
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in _STOP_WORDS
    )


def _money_targets(text: str) -> set[str]:
    targets = {
        match.group(0).lower().replace(",", "")
        for match in re.finditer(r"(?:[$€]\s*)?\d+(?:\.\d+)?\s*k", text, re.I)
    }
    targets.update(
        match.group(0).lower().replace(",", "")
        for match in re.finditer(r"[$€]\s*\d{3,}", text, re.I)
    )
    return targets


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


def _is_dating_logistics(
    candidate: dict[str, Any],
    parent_plan: dict[str, Any],
) -> bool:
    text = _candidate_text(candidate)
    tokens = _tokens(text)
    plan_type = str(candidate.get("plan_type") or parent_plan.get("plan_type") or "").lower()
    if plan_type != "dating" and "melissa" not in tokens:
        return False
    return bool(tokens & {"date", "dinner", "monday", "restaurant", "outing", "meetup"})


def _is_historical_context(text: str) -> bool:
    tokens = _tokens(text)
    return bool(tokens & {"told", "said", "invited", "hug", "matcha", "fired", "quit"})


def _is_first_million_exploration(text: str) -> bool:
    return "first million" in text or {"million", "worth"} <= _tokens(text)


def _is_badge_like_achievement(candidate: dict[str, Any]) -> bool:
    text = _candidate_text(candidate)
    tokens = _tokens(text)
    if _money_targets(text):
        return True
    if re.search(r"\b\d+\s*(?:%|percent|users?|clients?|months?|weeks?)\b", text):
        return True
    achievement_terms = {
        "achieve",
        "achieved",
        "approval",
        "approved",
        "complete",
        "completed",
        "finish",
        "finished",
        "hit",
        "launch",
        "launched",
        "mvp",
        "reach",
        "reached",
        "secure",
        "secured",
        "ship",
        "shipped",
        "submit",
        "submitted",
    }
    if tokens & achievement_terms:
        return True
    if tokens & {"application", "citizenship", "residency", "visa"} and tokens & {
        "italian",
        "italy",
        "estonia",
        "portugal",
        "nomad",
        "digital",
    }:
        return True
    return False


def _has_strategy_signal(text: str) -> bool:
    tokens = _tokens(text)
    return bool(
        tokens
        & {
            "route",
            "strategy",
            "through",
            "using",
            "supported",
            "because",
            "plan",
            "launch",
            "apply",
            "build",
            "gain",
            "lift",
            "move",
            "track",
        }
    )


def _has_success_signal(text: str) -> bool:
    tokens = _tokens(text)
    return bool(
        tokens
        & {
            "success",
            "successful",
            "achieve",
            "achieved",
            "stable",
            "ready",
            "approved",
            "launched",
            "revenue",
            "income",
            "living",
        }
    )


def _has_timeline_or_target(text: str) -> bool:
    if _money_targets(text):
        return True
    return bool(
        re.search(
            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december|week|month|year|next|by)\b",
            text,
            re.I,
        )
    )


def _append_unique_detail(existing: str, detail: str) -> str:
    existing = _clean(existing)
    detail = _clean(detail)
    if not detail:
        return existing
    if not existing:
        return detail
    if _normalize_title(detail) in _normalize_title(existing):
        return existing
    return f"{existing} Additional context: {detail}"


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
