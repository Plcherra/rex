import re
from datetime import date, datetime, timezone
from typing import Any, Optional

from app.models.accountability import (
    AccountabilityContext,
    AccountabilitySignal,
    AccountabilitySourceRef,
)
from app.services.commitment_service import is_open_commitment
from app.services.entity_service import (
    entity_event_accountability_text,
    is_active_entity_event,
)
from app.services.memory_service import (
    is_active_memory,
    memory_accountability_text,
)
from app.services.plan_service import is_active_plan, is_open_milestone
from app.services.rule_service import is_active_rule


RULE_CATEGORY_TERMS = {
    "transport": {
        "cab",
        "lyft",
        "ride",
        "rideshare",
        "taxi",
        "uber",
    },
    "food_delivery": {
        "delivery",
        "doordash",
        "door dash",
        "grubhub",
        "ubereats",
        "uber eats",
    },
    "coffee": {
        "coffee",
        "dunkin",
        "latte",
        "starbucks",
    },
    "rent": {
        "landlord",
        "lease",
        "rent",
    },
}
GENERIC_RULE_TERMS = {
    "budget",
    "cap",
    "caps",
    "delivery",
    "doordash",
    "door dash",
    "grocery",
    "groceries",
    "lyft",
    "netflix",
    "rent",
    "subscription",
    "subscriptions",
    "uber",
}
VIOLATION_ACTION_TERMS = {
    "bought",
    "grabbed",
    "ordered",
    "paid",
    "renewed",
    "spent",
    "took",
    "used",
}
NEGATION_TERMS = {
    "avoid",
    "cancel",
    "canceled",
    "delete",
    "deleted",
    "didnt",
    "didn't",
    "dont",
    "don't",
    "no",
    "not",
    "stop",
    "stopped",
    "without",
}
COMPLETION_TERMS = {
    "completed",
    "did",
    "done",
    "finished",
    "kept",
    "made",
    "sent",
    "submitted",
    "went",
    "worked",
}
FOLLOW_UP_AGE_DAYS = 7
PLAN_STALL_DAYS = 14
UPCOMING_MILESTONE_DAYS = 7
PATTERN_LOOKBACK_DAYS = 30
PATTERN_MIN_OCCURRENCES = 3
SHORT_MEANINGFUL_TERMS = {"app", "ios", "rex"}
PROGRESS_TERMS = {
    "advanced",
    "built",
    "closed",
    "finished",
    "fixed",
    "improved",
    "launched",
    "made",
    "moved",
    "progress",
    "shipped",
    "started",
    "worked",
}
PATTERN_CATEGORIES = {
    "delivery_spending": {
        "label": "delivery food",
        "terms": {
            "delivery",
            "doordash",
            "door dash",
            "grubhub",
            "ubereats",
            "uber eats",
        },
    },
    "transport_spending": {
        "label": "rideshare",
        "terms": {
            "cab",
            "lyft",
            "rideshare",
            "taxi",
            "uber",
        },
    },
    "coffee_spending": {
        "label": "coffee spending",
        "terms": {
            "coffee",
            "dunkin",
            "latte",
            "starbucks",
        },
    },
    "missed_commitments": {
        "label": "missed commitments",
        "terms": {
            "missed",
            "overdue",
            "skipped",
            "didn't do",
            "did not do",
            "forgot",
        },
    },
    "dating_anxiety": {
        "label": "dating hesitation",
        "terms": {
            "anxious",
            "date",
            "dating",
            "hesitated",
            "nervous",
            "passive",
            "submissive",
        },
    },
}


class AccountabilityService:
    async def analyze_signals(
        self,
        *,
        message: str,
        time_context: Optional[dict[str, Any]] = None,
        personal_rules: Optional[list[dict]] = None,
        commitments: Optional[list[dict]] = None,
        plans: Optional[list[dict]] = None,
        plan_milestones: Optional[list[dict]] = None,
        entity_events: Optional[list[dict]] = None,
        relevant_memories: Optional[list[dict]] = None,
    ) -> list[AccountabilitySignal]:
        context = await self.analyze(
            message=message,
            time_context=time_context,
            personal_rules=personal_rules,
            commitments=commitments,
            plans=plans,
            plan_milestones=plan_milestones,
            entity_events=entity_events,
            relevant_memories=relevant_memories,
        )
        return context.signals

    async def analyze(
        self,
        *,
        message: str,
        time_context: Optional[dict[str, Any]] = None,
        personal_rules: Optional[list[dict]] = None,
        commitments: Optional[list[dict]] = None,
        plans: Optional[list[dict]] = None,
        plan_milestones: Optional[list[dict]] = None,
        entity_events: Optional[list[dict]] = None,
        relevant_memories: Optional[list[dict]] = None,
    ) -> AccountabilityContext:
        current_time = _current_time(time_context)
        signals = [
            *self._detect_rule_violations(message, personal_rules or []),
            *self._detect_commitment_signals(
                message=message,
                commitments=commitments or [],
                current_time=current_time,
            ),
            *self._detect_plan_signals(
                message=message,
                plans=plans or [],
                plan_milestones=plan_milestones or [],
                current_time=current_time,
            ),
            *self._detect_repeated_patterns(
                message=message,
                entity_events=entity_events or [],
                relevant_memories=relevant_memories or [],
                current_time=current_time,
            ),
        ]
        return AccountabilityContext(
            signals=signals,
            metadata={
                "message_character_count": len(message),
                "time_context_present": bool(time_context),
                "personal_rule_count": len(personal_rules or []),
                "commitment_count": len(commitments or []),
                "plan_count": len(plans or []),
                "plan_milestone_count": len(plan_milestones or []),
                "entity_event_count": len(entity_events or []),
                "relevant_memory_count": len(relevant_memories or []),
            },
        )

    def active_signals(
        self,
        signals: list[AccountabilitySignal],
    ) -> list[AccountabilitySignal]:
        return [signal for signal in signals if signal.status == "active"]

    def _detect_rule_violations(
        self,
        message: str,
        personal_rules: list[dict],
    ) -> list[AccountabilitySignal]:
        normalized_message = _normalize_text(message)
        if not normalized_message:
            return []

        message_tokens = set(_tokens(normalized_message))
        action_terms = sorted(message_tokens & VIOLATION_ACTION_TERMS)
        if not action_terms:
            return []

        signals = []
        for rule in personal_rules:
            if not is_active_rule(rule):
                continue

            matched_terms = self._matched_rule_terms(normalized_message, rule)
            if not matched_terms:
                continue
            if self._is_negated_or_preventive(normalized_message, matched_terms):
                continue

            signals.append(
                self._rule_violation_signal(
                    rule=rule,
                    matched_terms=matched_terms,
                    action_terms=action_terms,
                )
            )
        return signals

    def _matched_rule_terms(self, normalized_message: str, rule: dict) -> list[str]:
        rule_terms = self._rule_terms(rule)
        return sorted(
            term for term in rule_terms if _contains_term(normalized_message, term)
        )

    def _rule_terms(self, rule: dict) -> set[str]:
        rule_type = str(rule.get("rule_type") or "").strip().lower()
        terms = set(RULE_CATEGORY_TERMS.get(rule_type, set()))
        terms.update(
            _normalize_text(value) for value in rule.get("trigger_keywords") or []
        )

        rule_text = _normalize_text(
            " ".join(
                str(rule.get(field) or "")
                for field in ("title", "rule_text")
            )
        )
        for term in GENERIC_RULE_TERMS:
            if _contains_term(rule_text, term):
                terms.add(term)

        return {term for term in terms if term}

    def _is_negated_or_preventive(
        self,
        normalized_message: str,
        matched_terms: list[str],
    ) -> bool:
        tokens = _tokens(normalized_message)
        for term in matched_terms:
            term_tokens = _tokens(term)
            if not term_tokens:
                continue
            for index in _term_start_indexes(tokens, term_tokens):
                window_start = max(index - 4, 0)
                window_end = min(index + len(term_tokens) + 3, len(tokens))
                nearby = set(tokens[window_start:window_end])
                if nearby & NEGATION_TERMS:
                    return True
        return False

    def _rule_violation_signal(
        self,
        *,
        rule: dict,
        matched_terms: list[str],
        action_terms: list[str],
    ) -> AccountabilitySignal:
        priority = _bounded_int(
            rule.get("priority"),
            default=3,
            minimum=1,
            maximum=5,
        )
        severity = "high" if priority >= 5 else "medium" if priority >= 4 else "low"
        confidence = min(
            0.95,
            0.55
            + (0.12 if matched_terms else 0)
            + (0.12 if action_terms else 0)
            + (0.08 if priority >= 4 else 0),
        )
        rule_title = str(rule.get("title") or "Personal rule").strip()
        rule_text = str(rule.get("rule_text") or "").strip()
        matched_summary = ", ".join(matched_terms[:4])

        return AccountabilitySignal(
            signal_type="rule_violation",
            title=f"Possible rule violation: {rule_title}",
            summary=f"Current message appears to conflict with rule: {rule_title}.",
            reason=(
                "The message contains action language "
                f"({', '.join(action_terms[:3])}) and matched rule trigger(s): "
                f"{matched_summary}."
            ),
            severity=severity,
            confidence=round(confidence, 2),
            source_refs=[
                AccountabilitySourceRef(
                    source_type="personal_rule",
                    source_id=str(rule.get("id")) if rule.get("id") else None,
                    title=rule_title,
                    excerpt=rule_text or None,
                )
            ],
            suggested_prompt=(
                f"You said this rule matters: {rule_text or rule_title}. "
                "This sounds like the same pattern again."
            ),
            recommended_action=(
                "Ask whether the action already happened, then hold the user to "
                "the rule or help them recover cleanly."
            ),
            metadata={
                "rule_type": rule.get("rule_type"),
                "matched_terms": matched_terms,
                "action_terms": action_terms,
                "rule_priority": priority,
                "enforcement_style": rule.get("enforcement_style"),
            },
        )

    def _detect_commitment_signals(
        self,
        *,
        message: str,
        commitments: list[dict],
        current_time: datetime,
    ) -> list[AccountabilitySignal]:
        normalized_message = _normalize_text(message)
        message_tokens = set(_tokens(normalized_message))
        signals = []

        for commitment in commitments:
            if not is_open_commitment(commitment):
                continue

            matched_terms = self._matched_commitment_terms(
                normalized_message,
                commitment,
            )
            if matched_terms and message_tokens & COMPLETION_TERMS:
                signals.append(
                    self._positive_follow_through_signal(
                        commitment=commitment,
                        matched_terms=matched_terms,
                    )
                )
                continue

            due_at = _parse_datetime(commitment.get("due_at"))
            if due_at is not None:
                if due_at < current_time:
                    signals.append(
                        self._missed_commitment_signal(
                            commitment=commitment,
                            due_at=due_at,
                            current_time=current_time,
                        )
                    )
                elif due_at.astimezone(current_time.tzinfo).date() == current_time.date():
                    signals.append(
                        self._due_today_commitment_signal(
                            commitment=commitment,
                            due_at=due_at,
                            current_time=current_time,
                        )
                    )
                continue

            last_checked_at = _parse_datetime(commitment.get("last_checked_at"))
            if self._needs_commitment_follow_up(commitment, last_checked_at, current_time):
                signals.append(
                    self._commitment_follow_up_signal(
                        commitment=commitment,
                        last_checked_at=last_checked_at,
                    )
                )

        return signals

    def _matched_commitment_terms(
        self,
        normalized_message: str,
        commitment: dict,
    ) -> list[str]:
        terms = self._commitment_terms(commitment)
        return sorted(
            term for term in terms if _contains_term(normalized_message, term)
        )

    def _commitment_terms(self, commitment: dict) -> set[str]:
        text = _normalize_text(
            " ".join(
                str(commitment.get(field) or "")
                for field in ("title", "commitment_text", "commitment_type")
            )
        )
        stop_terms = {
            "about",
            "again",
            "commitment",
            "need",
            "open",
            "task",
            "that",
            "the",
            "this",
            "will",
            "with",
        }
        return {
            token
            for token in _tokens(text)
            if len(token) >= 4 and token not in stop_terms
        }

    def _needs_commitment_follow_up(
        self,
        commitment: dict,
        last_checked_at: Optional[datetime],
        current_time: datetime,
    ) -> bool:
        priority = _bounded_int(commitment.get("priority"), default=3, minimum=1, maximum=5)
        if priority < 4:
            return False
        if last_checked_at is None:
            return True
        return (current_time - last_checked_at).days >= FOLLOW_UP_AGE_DAYS

    def _missed_commitment_signal(
        self,
        *,
        commitment: dict,
        due_at: datetime,
        current_time: datetime,
    ) -> AccountabilitySignal:
        priority = _bounded_int(commitment.get("priority"), default=3, minimum=1, maximum=5)
        overdue_hours = max((current_time - due_at).total_seconds() / 3600, 0)
        severity = "high" if priority >= 5 or overdue_hours >= 24 else "medium"
        title = str(commitment.get("title") or "Commitment").strip()
        text = str(commitment.get("commitment_text") or "").strip()

        return AccountabilitySignal(
            signal_type="missed_commitment",
            title=f"Missed commitment: {title}",
            summary=f"The commitment is overdue: {title}.",
            reason=f"Due at {due_at.isoformat()} and still marked open.",
            severity=severity,
            confidence=0.9,
            source_refs=[self._commitment_source_ref(commitment)],
            suggested_prompt=(
                f"You committed to this: {text or title}. It is overdue now."
            ),
            recommended_action=(
                "Ask whether it was completed. If not, get a concrete recovery step."
            ),
            metadata={
                "commitment_status": commitment.get("status"),
                "commitment_priority": priority,
                "due_at": due_at.isoformat(),
                "overdue_hours": round(overdue_hours, 2),
            },
        )

    def _due_today_commitment_signal(
        self,
        *,
        commitment: dict,
        due_at: datetime,
        current_time: datetime,
    ) -> AccountabilitySignal:
        priority = _bounded_int(commitment.get("priority"), default=3, minimum=1, maximum=5)
        title = str(commitment.get("title") or "Commitment").strip()
        text = str(commitment.get("commitment_text") or "").strip()
        hours_until_due = max((due_at - current_time).total_seconds() / 3600, 0)

        return AccountabilitySignal(
            signal_type="upcoming_deadline",
            title=f"Commitment due today: {title}",
            summary=f"The commitment is due today: {title}.",
            reason=f"Due at {due_at.isoformat()} and still marked open.",
            severity="medium" if priority >= 4 else "low",
            confidence=0.86,
            source_refs=[self._commitment_source_ref(commitment)],
            suggested_prompt=f"This is due today: {text or title}.",
            recommended_action="Ask for the next concrete action before the day slips.",
            metadata={
                "subtype": "commitment_due_today",
                "commitment_status": commitment.get("status"),
                "commitment_priority": priority,
                "due_at": due_at.isoformat(),
                "hours_until_due": round(hours_until_due, 2),
            },
        )

    def _positive_follow_through_signal(
        self,
        *,
        commitment: dict,
        matched_terms: list[str],
    ) -> AccountabilitySignal:
        title = str(commitment.get("title") or "Commitment").strip()
        text = str(commitment.get("commitment_text") or "").strip()

        return AccountabilitySignal(
            signal_type="positive_follow_through",
            title=f"Follow-through reported: {title}",
            summary=f"The user appears to report completing: {title}.",
            reason=(
                "The current message uses completion language and matched "
                f"commitment terms: {', '.join(matched_terms[:4])}."
            ),
            severity="info",
            confidence=0.78,
            source_refs=[self._commitment_source_ref(commitment)],
            suggested_prompt=f"Looks like you followed through on: {text or title}.",
            recommended_action=(
                "Acknowledge the follow-through and ask if this should be marked complete."
            ),
            metadata={
                "matched_terms": matched_terms,
                "commitment_status": commitment.get("status"),
                "subtype": "reported_completion",
            },
        )

    def _commitment_follow_up_signal(
        self,
        *,
        commitment: dict,
        last_checked_at: Optional[datetime],
    ) -> AccountabilitySignal:
        priority = _bounded_int(commitment.get("priority"), default=3, minimum=1, maximum=5)
        title = str(commitment.get("title") or "Commitment").strip()
        text = str(commitment.get("commitment_text") or "").strip()

        return AccountabilitySignal(
            signal_type="upcoming_deadline",
            title=f"Commitment needs follow-up: {title}",
            summary=f"High-priority commitment has no recent check-in: {title}.",
            reason="High-priority open commitment has no due date or recent check-in.",
            severity="low",
            confidence=0.68,
            source_refs=[self._commitment_source_ref(commitment)],
            suggested_prompt=f"Quick check-in on this commitment: {text or title}.",
            recommended_action="Ask whether it is still active and what the next step is.",
            metadata={
                "subtype": "commitment_follow_up",
                "commitment_status": commitment.get("status"),
                "commitment_priority": priority,
                "last_checked_at": last_checked_at.isoformat()
                if last_checked_at
                else None,
            },
        )

    def _commitment_source_ref(self, commitment: dict) -> AccountabilitySourceRef:
        return AccountabilitySourceRef(
            source_type="commitment",
            source_id=str(commitment.get("id")) if commitment.get("id") else None,
            title=str(commitment.get("title") or "Commitment"),
            excerpt=str(commitment.get("commitment_text") or "") or None,
        )

    def _detect_plan_signals(
        self,
        *,
        message: str,
        plans: list[dict],
        plan_milestones: list[dict],
        current_time: datetime,
    ) -> list[AccountabilitySignal]:
        normalized_message = _normalize_text(message)
        message_tokens = set(_tokens(normalized_message))
        active_plans = {
            str(plan.get("id")): plan
            for plan in plans
            if plan.get("id") and is_active_plan(plan)
        }
        signals: list[AccountabilitySignal] = []

        for plan in active_plans.values():
            matched_terms = self._matched_plan_terms(normalized_message, plan)
            if matched_terms and message_tokens & PROGRESS_TERMS:
                signals.append(
                    self._plan_progress_signal(
                        plan=plan,
                        matched_terms=matched_terms,
                    )
                )

            target_date = _parse_date(plan.get("target_date"))
            if target_date is not None and target_date < current_time.date():
                signals.append(
                    self._plan_target_drift_signal(
                        plan=plan,
                        target_date=target_date,
                        current_time=current_time,
                    )
                )
                continue

            last_reviewed_at = _parse_datetime(plan.get("last_reviewed_at"))
            if self._is_plan_stalled(plan, last_reviewed_at, current_time):
                signals.append(
                    self._stalled_plan_signal(
                        plan=plan,
                        last_reviewed_at=last_reviewed_at,
                    )
                )

        for milestone in plan_milestones:
            if not is_open_milestone(milestone):
                continue
            plan = active_plans.get(str(milestone.get("plan_id")))
            if plan is None:
                continue

            matched_terms = self._matched_milestone_terms(
                normalized_message,
                milestone,
                plan,
            )
            if matched_terms and message_tokens & PROGRESS_TERMS:
                signals.append(
                    self._milestone_progress_signal(
                        milestone=milestone,
                        plan=plan,
                        matched_terms=matched_terms,
                    )
                )
                continue

            target_date = _parse_date(milestone.get("target_date"))
            if target_date is None:
                continue
            if target_date < current_time.date():
                signals.append(
                    self._overdue_milestone_signal(
                        milestone=milestone,
                        plan=plan,
                        target_date=target_date,
                        current_time=current_time,
                    )
                )
            elif (target_date - current_time.date()).days <= UPCOMING_MILESTONE_DAYS:
                signals.append(
                    self._upcoming_milestone_signal(
                        milestone=milestone,
                        plan=plan,
                        target_date=target_date,
                        current_time=current_time,
                    )
                )

        return signals

    def _matched_plan_terms(self, normalized_message: str, plan: dict) -> list[str]:
        terms = self._plan_terms(plan)
        return sorted(
            term for term in terms if _contains_term(normalized_message, term)
        )

    def _matched_milestone_terms(
        self,
        normalized_message: str,
        milestone: dict,
        plan: dict,
    ) -> list[str]:
        terms = self._plan_terms(plan) | self._milestone_terms(milestone)
        return sorted(
            term for term in terms if _contains_term(normalized_message, term)
        )

    def _plan_terms(self, plan: dict) -> set[str]:
        text = _normalize_text(
            " ".join(
                str(plan.get(field) or "")
                for field in ("title", "description", "desired_outcome", "plan_type")
            )
        )
        return _meaningful_terms(text)

    def _milestone_terms(self, milestone: dict) -> set[str]:
        text = _normalize_text(
            " ".join(
                str(milestone.get(field) or "")
                for field in ("title", "description", "milestone_type")
            )
        )
        return _meaningful_terms(text)

    def _is_plan_stalled(
        self,
        plan: dict,
        last_reviewed_at: Optional[datetime],
        current_time: datetime,
    ) -> bool:
        priority = _bounded_int(plan.get("priority"), default=3, minimum=1, maximum=5)
        if priority < 4:
            return False
        if last_reviewed_at is None:
            created_at = _parse_datetime(plan.get("created_at"))
            if created_at is None:
                return True
            last_reviewed_at = created_at
        return (current_time - last_reviewed_at).days >= PLAN_STALL_DAYS

    def _plan_progress_signal(
        self,
        *,
        plan: dict,
        matched_terms: list[str],
    ) -> AccountabilitySignal:
        title = str(plan.get("title") or "Plan").strip()
        description = str(plan.get("description") or "").strip()

        return AccountabilitySignal(
            signal_type="positive_follow_through",
            title=f"Plan progress reported: {title}",
            summary=f"The user appears to report progress on: {title}.",
            reason=(
                "The current message uses progress language and matched plan "
                f"terms: {', '.join(matched_terms[:4])}."
            ),
            severity="info",
            confidence=0.74,
            source_refs=[self._plan_source_ref(plan)],
            suggested_prompt=f"That sounds like progress on {title}.",
            recommended_action=(
                "Acknowledge the progress and ask whether the plan status or "
                "next milestone should be updated."
            ),
            metadata={
                "subtype": "plan_progress",
                "matched_terms": matched_terms,
                "plan_status": plan.get("status"),
            },
        )

    def _milestone_progress_signal(
        self,
        *,
        milestone: dict,
        plan: dict,
        matched_terms: list[str],
    ) -> AccountabilitySignal:
        title = str(milestone.get("title") or "Milestone").strip()

        return AccountabilitySignal(
            signal_type="positive_follow_through",
            title=f"Milestone progress reported: {title}",
            summary=f"The user appears to report progress on milestone: {title}.",
            reason=(
                "The current message uses progress language and matched milestone "
                f"terms: {', '.join(matched_terms[:4])}."
            ),
            severity="info",
            confidence=0.78,
            source_refs=[
                self._milestone_source_ref(milestone),
                self._plan_source_ref(plan),
            ],
            suggested_prompt=f"That sounds like progress on {title}.",
            recommended_action=(
                "Acknowledge the update and ask whether the milestone should be "
                "marked in progress or complete."
            ),
            metadata={
                "subtype": "milestone_progress",
                "matched_terms": matched_terms,
                "milestone_status": milestone.get("status"),
                "plan_id": plan.get("id"),
            },
        )

    def _plan_target_drift_signal(
        self,
        *,
        plan: dict,
        target_date: date,
        current_time: datetime,
    ) -> AccountabilitySignal:
        title = str(plan.get("title") or "Plan").strip()
        days_overdue = (current_time.date() - target_date).days
        priority = _bounded_int(plan.get("priority"), default=3, minimum=1, maximum=5)

        return AccountabilitySignal(
            signal_type="plan_drift",
            title=f"Plan target missed: {title}",
            summary=f"The active plan target date has passed: {title}.",
            reason=f"Target date was {target_date.isoformat()} and plan is still active.",
            severity="high" if priority >= 5 or days_overdue >= 14 else "medium",
            confidence=0.86,
            source_refs=[self._plan_source_ref(plan)],
            suggested_prompt=f"The target for {title} has passed.",
            recommended_action=(
                "Ask if the plan should be rescheduled, completed, or abandoned."
            ),
            metadata={
                "subtype": "plan_target_missed",
                "target_date": target_date.isoformat(),
                "days_overdue": days_overdue,
                "plan_priority": priority,
            },
        )

    def _stalled_plan_signal(
        self,
        *,
        plan: dict,
        last_reviewed_at: Optional[datetime],
    ) -> AccountabilitySignal:
        title = str(plan.get("title") or "Plan").strip()
        priority = _bounded_int(plan.get("priority"), default=3, minimum=1, maximum=5)

        return AccountabilitySignal(
            signal_type="plan_drift",
            title=f"Plan needs review: {title}",
            summary=f"High-priority plan has no recent review: {title}.",
            reason="The active plan is high priority and has not been reviewed recently.",
            severity="low" if priority < 5 else "medium",
            confidence=0.68,
            source_refs=[self._plan_source_ref(plan)],
            suggested_prompt=f"Quick review on {title}: what changed since last check-in?",
            recommended_action=(
                "Ask for current status, blockers, and the next concrete step."
            ),
            metadata={
                "subtype": "stalled_plan",
                "plan_priority": priority,
                "last_reviewed_at": last_reviewed_at.isoformat()
                if last_reviewed_at
                else None,
            },
        )

    def _overdue_milestone_signal(
        self,
        *,
        milestone: dict,
        plan: dict,
        target_date: date,
        current_time: datetime,
    ) -> AccountabilitySignal:
        title = str(milestone.get("title") or "Milestone").strip()
        days_overdue = (current_time.date() - target_date).days
        priority = _bounded_int(
            milestone.get("priority"),
            default=_bounded_int(plan.get("priority"), default=3, minimum=1, maximum=5),
            minimum=1,
            maximum=5,
        )

        return AccountabilitySignal(
            signal_type="plan_drift",
            title=f"Milestone overdue: {title}",
            summary=f"Plan milestone is overdue: {title}.",
            reason=(
                f"Milestone target date was {target_date.isoformat()} and "
                "it is still open."
            ),
            severity="high" if priority >= 5 or days_overdue >= 7 else "medium",
            confidence=0.88,
            source_refs=[
                self._milestone_source_ref(milestone),
                self._plan_source_ref(plan),
            ],
            suggested_prompt=f"The milestone {title} is overdue.",
            recommended_action=(
                "Ask whether it is complete. If not, help reset a realistic next step."
            ),
            metadata={
                "subtype": "overdue_milestone",
                "target_date": target_date.isoformat(),
                "days_overdue": days_overdue,
                "milestone_status": milestone.get("status"),
                "plan_id": plan.get("id"),
            },
        )

    def _upcoming_milestone_signal(
        self,
        *,
        milestone: dict,
        plan: dict,
        target_date: date,
        current_time: datetime,
    ) -> AccountabilitySignal:
        title = str(milestone.get("title") or "Milestone").strip()
        days_until_due = (target_date - current_time.date()).days

        return AccountabilitySignal(
            signal_type="upcoming_deadline",
            title=f"Milestone coming up: {title}",
            summary=f"Plan milestone is coming up: {title}.",
            reason=f"Milestone target date is {target_date.isoformat()}.",
            severity="medium" if days_until_due <= 2 else "low",
            confidence=0.82,
            source_refs=[
                self._milestone_source_ref(milestone),
                self._plan_source_ref(plan),
            ],
            suggested_prompt=f"{title} is due soon.",
            recommended_action=(
                "Connect the current message to the milestone and ask for the next step."
            ),
            metadata={
                "subtype": "upcoming_milestone",
                "target_date": target_date.isoformat(),
                "days_until_due": days_until_due,
                "milestone_status": milestone.get("status"),
                "plan_id": plan.get("id"),
            },
        )

    def _plan_source_ref(self, plan: dict) -> AccountabilitySourceRef:
        return AccountabilitySourceRef(
            source_type="plan",
            source_id=str(plan.get("id")) if plan.get("id") else None,
            title=str(plan.get("title") or "Plan"),
            excerpt=str(plan.get("description") or plan.get("desired_outcome") or "")
            or None,
        )

    def _milestone_source_ref(self, milestone: dict) -> AccountabilitySourceRef:
        return AccountabilitySourceRef(
            source_type="plan_milestone",
            source_id=str(milestone.get("id")) if milestone.get("id") else None,
            title=str(milestone.get("title") or "Milestone"),
            excerpt=str(milestone.get("description") or "") or None,
        )

    def _detect_repeated_patterns(
        self,
        *,
        message: str,
        entity_events: list[dict],
        relevant_memories: list[dict],
        current_time: datetime,
    ) -> list[AccountabilitySignal]:
        normalized_message = _normalize_text(message)
        matched_categories = self._matched_pattern_categories(normalized_message)
        if not matched_categories:
            return []

        signals = []
        for category in matched_categories:
            related_records = self._related_pattern_records(
                category=category,
                entity_events=entity_events,
                relevant_memories=relevant_memories,
                current_time=current_time,
            )
            total_occurrences = len(related_records) + 1
            if total_occurrences < PATTERN_MIN_OCCURRENCES:
                continue

            signals.append(
                self._repeated_pattern_signal(
                    category=category,
                    related_records=related_records,
                    total_occurrences=total_occurrences,
                )
            )
        return signals

    def _matched_pattern_categories(self, normalized_message: str) -> list[str]:
        categories = []
        for category, config in PATTERN_CATEGORIES.items():
            terms = set(config["terms"])
            if self._matched_pattern_terms(normalized_message, terms):
                categories.append(category)
        return categories

    def _related_pattern_records(
        self,
        *,
        category: str,
        entity_events: list[dict],
        relevant_memories: list[dict],
        current_time: datetime,
    ) -> list[dict]:
        terms = set(PATTERN_CATEGORIES[category]["terms"])
        records = []

        for memory in relevant_memories:
            if not is_active_memory(memory):
                continue
            if not _is_recent_pattern_record(memory, current_time):
                continue
            text = _normalize_text(memory_accountability_text(memory))
            matched_terms = self._matched_pattern_terms(text, terms)
            if matched_terms:
                records.append(
                    {
                        "source_type": "long_term_memory",
                        "source": memory,
                        "matched_terms": matched_terms,
                        "timestamp": _pattern_record_time(memory),
                    }
                )

        for event in entity_events:
            if not is_active_entity_event(event):
                continue
            if not _is_recent_pattern_record(event, current_time):
                continue
            text = _normalize_text(entity_event_accountability_text(event))
            matched_terms = self._matched_pattern_terms(text, terms)
            if matched_terms:
                records.append(
                    {
                        "source_type": "entity_event",
                        "source": event,
                        "matched_terms": matched_terms,
                        "timestamp": _pattern_record_time(event),
                    }
                )

        records.sort(
            key=lambda record: record["timestamp"] or datetime.min.replace(
                tzinfo=timezone.utc
            ),
            reverse=True,
        )
        return records

    def _matched_pattern_terms(self, normalized_text: str, terms: set[str]) -> list[str]:
        return sorted(
            term for term in terms if _contains_term(normalized_text, term)
        )

    def _repeated_pattern_signal(
        self,
        *,
        category: str,
        related_records: list[dict],
        total_occurrences: int,
    ) -> AccountabilitySignal:
        config = PATTERN_CATEGORIES[category]
        label = str(config["label"])
        matched_terms = sorted(
            {
                term
                for record in related_records
                for term in record["matched_terms"]
            }
        )
        source_counts = {
            "long_term_memory": sum(
                1 for record in related_records if record["source_type"] == "long_term_memory"
            ),
            "entity_event": sum(
                1 for record in related_records if record["source_type"] == "entity_event"
            ),
        }

        return AccountabilitySignal(
            signal_type="repeated_pattern",
            title=f"Repeated pattern: {label}",
            summary=(
                f"This looks like the latest instance of a recurring {label} pattern."
            ),
            reason=(
                f"Found {len(related_records)} recent related record(s), plus the "
                "current message, inside the lookback window."
            ),
            severity="high" if total_occurrences >= 5 else "medium",
            confidence=min(0.92, 0.58 + (0.08 * total_occurrences)),
            source_refs=[
                self._pattern_source_ref(record)
                for record in related_records[:3]
            ],
            suggested_prompt=(
                f"This is not isolated. It matches a recent {label} pattern."
            ),
            recommended_action=(
                "Name the pattern directly, then ask what changed this time and "
                "what concrete adjustment prevents the next repeat."
            ),
            metadata={
                "category": category,
                "label": label,
                "matched_terms": matched_terms,
                "historical_occurrence_count": len(related_records),
                "occurrence_count": total_occurrences,
                "lookback_days": PATTERN_LOOKBACK_DAYS,
                "source_counts": source_counts,
            },
        )

    def _pattern_source_ref(self, record: dict) -> AccountabilitySourceRef:
        source = record["source"]
        source_type = record["source_type"]
        if source_type == "long_term_memory":
            return AccountabilitySourceRef(
                source_type="long_term_memory",
                source_id=str(source.get("id")) if source.get("id") else None,
                title=str(source.get("memory_type") or "Memory"),
                excerpt=str(source.get("content") or "") or None,
                metadata={"matched_terms": record["matched_terms"]},
            )

        return AccountabilitySourceRef(
            source_type="entity_event",
            source_id=str(source.get("id")) if source.get("id") else None,
            title=str(source.get("title") or source.get("event_type") or "Event"),
            excerpt=str(source.get("content") or "") or None,
            metadata={"matched_terms": record["matched_terms"]},
        )


def _contains_term(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return bool(re.search(rf"\b{re.escape(term)}\b", text))


def _normalize_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = text.replace("’", "'")
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", _normalize_text(text))


def _term_start_indexes(tokens: list[str], term_tokens: list[str]) -> list[int]:
    if not tokens or not term_tokens:
        return []
    width = len(term_tokens)
    return [
        index
        for index in range(0, len(tokens) - width + 1)
        if tokens[index : index + width] == term_tokens
    ]


def _current_time(time_context: Optional[dict[str, Any]]) -> datetime:
    parsed = _parse_datetime((time_context or {}).get("iso_timestamp"))
    return parsed or datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def _pattern_record_time(record: dict) -> Optional[datetime]:
    for field in (
        "occurred_at",
        "created_at",
        "updated_at",
        "last_accessed_at",
    ):
        parsed = _parse_datetime(record.get(field))
        if parsed is not None:
            return parsed
    return None


def _is_recent_pattern_record(record: dict, current_time: datetime) -> bool:
    timestamp = _pattern_record_time(record)
    if timestamp is None:
        return True
    age_days = (current_time - timestamp).days
    return age_days <= PATTERN_LOOKBACK_DAYS


def _meaningful_terms(text: str) -> set[str]:
    stop_terms = {
        "about",
        "active",
        "again",
        "checkpoint",
        "deadline",
        "goal",
        "need",
        "open",
        "other",
        "plan",
        "task",
        "that",
        "the",
        "this",
        "will",
        "with",
    }
    return {
        token
        for token in _tokens(text)
        if (len(token) >= 4 or token in SHORT_MEANINGFUL_TERMS)
        and token not in stop_terms
    }


def _bounded_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))
