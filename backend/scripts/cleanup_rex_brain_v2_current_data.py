from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.http_client import shutdown_http_client, startup_http_client
from app.services.memory_service import SupabaseMemoryService


CLEANUP_VERSION = 2

RELOCATION_PLAN_TITLE = "Move out of the country next year"
RELOCATION_PLAN_DESCRIPTION = (
    "Move out of the country next year after building reliable remote income. "
    "Primary route is Italian citizenship by descent through the user's "
    "great-grandmother. If law changes block eligibility, use Portugal D7 or "
    "digital nomad residency as the backup route because Portugal can lead to "
    "residency/citizenship over time. Greece is a visit-only preference, not "
    "the primary relocation destination. Income target is about $3k/month by "
    "the end of this year, scaling toward $5k/month profit or $5k-$8k/month "
    "revenue before moving."
)
RELOCATION_PLAN_OUTCOME = (
    "Ready to leave the USA with enough remote income and a clear Italy-first, "
    "Portugal-backup immigration route."
)

APP_PLAN_TITLE = "Launch and monetize Clarity, EchoDesk, and FlowForce"
APP_PLAN_DESCRIPTION = (
    "Launch three apps to build portfolio strength, create subscription "
    "revenue, and improve Upwork/custom project opportunities. First launch is "
    "Clarity in 2-3 weeks, containing the Rex personal advisor and financial "
    "transaction access. EchoDesk follows around mid to late next month, then "
    "FlowForce by the end of the following month. Revenue can come from app "
    "subscriptions, Upwork, or custom projects."
)
APP_PLAN_OUTCOME = (
    "Clarity, EchoDesk, and FlowForce are live enough to attract users, revenue, "
    "or better client work."
)

MELISSA_PLAN_TITLE = "Melissa follow-up"
MELISSA_PLAN_DESCRIPTION = (
    "The user already asked Melissa out. She said she would respond, and the "
    "current read is that she is likely not interested. Keep this as one simple "
    "follow-up plan only if she replies or there is a clear next action."
)
MELISSA_PLAN_OUTCOME = "Know whether Melissa wants to continue the date plan."

RELOCATION_MILESTONES = [
    (
        "Italian citizenship by descent eligibility confirmed",
        "Confirm whether the great-grandmother citizenship route is still viable.",
    ),
    (
        "Portugal D7 or digital nomad backup route selected",
        "Choose the Portugal backup route if Italian citizenship is blocked.",
    ),
    (
        "Reach $3k/month revenue by end of year",
        "Hit the first income gate from apps, Upwork, or custom projects.",
    ),
    (
        "Reach about $5k/month before moving",
        "Reach the move-ready income level before leaving the country.",
    ),
]

APP_MILESTONES = [
    (
        "Clarity launched",
        "Launch the first app, with Rex advisor and financial clarity features inside.",
    ),
    ("EchoDesk launched", "Launch EchoDesk after Clarity."),
    ("FlowForce launched", "Launch FlowForce after EchoDesk."),
    (
        "First app or client revenue",
        "Earn first revenue from subscriptions, Upwork, or custom project work.",
    ),
]


@dataclass
class CleanupOperation:
    action: str
    record_type: str
    record_id: str | None
    title: str
    reason: str
    updates: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "record_type": self.record_type,
            "record_id": self.record_id,
            "title": self.title,
            "reason": self.reason,
            "updates": self.updates,
        }


@dataclass
class CleanupReport:
    dry_run: bool
    scanned: dict[str, int]
    operations: list[CleanupOperation] = field(default_factory=list)
    applied: list[dict[str, Any]] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "scanned": self.scanned,
            "operations": [operation.as_dict() for operation in self.operations],
            "applied": self.applied,
            "verification": self.verification,
            "errors": self.errors,
        }


async def cleanup_rex_brain_v2_current_data(
    memory_service: SupabaseMemoryService,
    *,
    apply: bool = False,
    limit: int = 500,
) -> CleanupReport:
    plans, milestones, commitments, entities = await asyncio.gather(
        memory_service.list_plans(active=True, limit=limit),
        memory_service.list_plan_milestones(active=True, limit=limit),
        memory_service.list_commitments(active=True, limit=limit),
        memory_service.list_entities(active=True, limit=limit),
    )
    report = CleanupReport(
        dry_run=not apply,
        scanned={
            "plans": len(plans),
            "milestones": len(milestones),
            "commitments": len(commitments),
            "entities": len(entities),
        },
    )
    report.operations = build_cleanup_operations(
        plans=plans,
        milestones=milestones,
        commitments=commitments,
        entities=entities,
    )

    if apply:
        report.applied = await _apply_operations(memory_service, report.operations)
        plans, milestones, commitments, entities = await asyncio.gather(
            memory_service.list_plans(active=True, limit=limit),
            memory_service.list_plan_milestones(active=True, limit=limit),
            memory_service.list_commitments(active=True, limit=limit),
            memory_service.list_entities(active=True, limit=limit),
        )
        follow_up_operations = build_cleanup_operations(
            plans=plans,
            milestones=milestones,
            commitments=commitments,
            entities=entities,
        )
        if follow_up_operations:
            report.operations.extend(follow_up_operations)
            report.applied.extend(
                await _apply_operations(memory_service, follow_up_operations)
            )
            plans, milestones, commitments, entities = await asyncio.gather(
                memory_service.list_plans(active=True, limit=limit),
                memory_service.list_plan_milestones(active=True, limit=limit),
                memory_service.list_commitments(active=True, limit=limit),
                memory_service.list_entities(active=True, limit=limit),
            )

    report.verification = verify_cleanup_state(
        plans=plans,
        milestones=milestones,
        commitments=commitments,
        entities=entities,
        applied=report.applied,
    )
    return report


def build_cleanup_operations(
    *,
    plans: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    commitments: list[dict[str, Any]],
    entities: list[dict[str, Any]],
) -> list[CleanupOperation]:
    operations: list[CleanupOperation] = []
    plan_by_id = {str(plan.get("id")): plan for plan in plans if plan.get("id")}

    relocation_plan = _select_plan(plans, _is_relocation_plan)
    app_plan = _select_plan(plans, _is_app_plan)
    melissa_plan = _select_plan(plans, _is_melissa_plan)

    if not app_plan and _has_app_evidence(plans=plans, milestones=milestones):
        operations.append(_create_app_plan_operation())

    if relocation_plan:
        operations.append(
            _update_plan_operation(
                relocation_plan,
                title=RELOCATION_PLAN_TITLE,
                description=RELOCATION_PLAN_DESCRIPTION,
                desired_outcome=RELOCATION_PLAN_OUTCOME,
                reason="make relocation plan Portugal/Italy aligned and remove Greece as primary target",
            )
        )
        relocation_milestone_operations = _canonical_milestone_operations(
            milestones=milestones,
            plan=relocation_plan,
            canonical=RELOCATION_MILESTONES,
            reason="keep only achievement-style relocation milestones",
        )
        operations.extend(relocation_milestone_operations)
        operations.extend(
            _archive_noisy_milestones(
                milestones=milestones,
                plan=relocation_plan,
                keep_titles={title for title, _ in RELOCATION_MILESTONES},
                keep_ids=_operation_record_ids(relocation_milestone_operations),
                matcher=_is_noisy_relocation_milestone,
            )
        )

    if app_plan:
        operations.append(
            _update_plan_operation(
                app_plan,
                title=APP_PLAN_TITLE,
                description=APP_PLAN_DESCRIPTION,
                desired_outcome=APP_PLAN_OUTCOME,
                reason="align app plan around Clarity, EchoDesk, and FlowForce",
            )
        )
        app_milestone_operations = _canonical_milestone_operations(
            milestones=milestones,
            plan=app_plan,
            canonical=APP_MILESTONES,
            reason="keep only launch and revenue achievement milestones",
        )
        operations.extend(app_milestone_operations)
        operations.extend(
            _archive_noisy_milestones(
                milestones=milestones,
                plan=app_plan,
                keep_titles={title for title, _ in APP_MILESTONES},
                keep_ids=_operation_record_ids(app_milestone_operations),
                matcher=_is_noisy_app_milestone,
            )
        )

    if melissa_plan:
        operations.append(
            _update_plan_operation(
                melissa_plan,
                title=MELISSA_PLAN_TITLE,
                description=MELISSA_PLAN_DESCRIPTION,
                desired_outcome=MELISSA_PLAN_OUTCOME,
                reason="collapse Melissa duplicates into one follow-up plan",
            )
        )
        operations.extend(
            _archive_noisy_milestones(
                milestones=milestones,
                plan=melissa_plan,
                keep_titles=set(),
                matcher=_is_melissa_milestone,
            )
        )

    canonical_plan_ids = {
        str(plan.get("id"))
        for plan in (relocation_plan, app_plan, melissa_plan)
        if plan and plan.get("id")
    }
    for plan in plans:
        plan_id = str(plan.get("id") or "")
        if plan_id in canonical_plan_ids:
            continue
        if _should_archive_plan(plan):
            target = _target_plan_for_archive(plan, relocation_plan, app_plan, melissa_plan)
            operations.append(_archive_plan_operation(plan, target))

    operations.extend(_entity_correction_operations(entities))
    operations.extend(_orphan_milestone_operations(milestones, plan_by_id))
    operations.extend(_duplicate_commitment_operations(commitments))
    operations.extend(_orphan_commitment_operations(commitments, plan_by_id))
    return _dedupe_operations(operations)


def verify_cleanup_state(
    *,
    plans: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    commitments: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    applied: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_plans = [plan for plan in plans if _active(plan)]
    open_milestones = [
        milestone
        for milestone in milestones
        if _active(milestone)
        and str(milestone.get("status") or "open") in {"open", "in_progress"}
    ]
    stephanie_bad = [
        entity
        for entity in entities
        if _active(entity)
        and "stephanie" in _entity_text(entity)
        and "got fired at the beginning of this year" in _entity_text(entity)
    ]
    greece_primary = [
        plan
        for plan in active_plans
        if "relocate to greece" in _record_text(plan)
        or "live in greece" in _record_text(plan)
    ]
    noisy_melissa = [
        milestone
        for milestone in open_milestones
        if "melissa" in _record_text(milestone)
    ]
    noisy_first_million = [
        milestone
        for milestone in open_milestones
        if "first million" in _record_text(milestone)
    ]
    wrong_app_names = [
        milestone
        for milestone in open_milestones
        if any(name in _record_text(milestone) for name in ("ecodesk", "flow force"))
    ]
    failures = []
    failed_operations = [item for item in applied or [] if not item.get("success")]
    active_plan_ids = {str(plan.get("id") or "") for plan in active_plans}
    orphan_milestones = [
        milestone
        for milestone in open_milestones
        if str(milestone.get("plan_id") or "") not in active_plan_ids
    ]
    app_plans = [
        plan
        for plan in active_plans
        if _normalize(plan.get("title")) == _normalize(APP_PLAN_TITLE)
    ]
    relocation_plans = [
        plan
        for plan in active_plans
        if _normalize(plan.get("title")) == _normalize(RELOCATION_PLAN_TITLE)
    ]
    missing_relocation_milestones = _missing_canonical_milestones(
        milestones,
        relocation_plans[0] if relocation_plans else None,
        RELOCATION_MILESTONES,
    )
    missing_app_milestones = _missing_canonical_milestones(
        milestones,
        app_plans[0] if app_plans else None,
        APP_MILESTONES,
    )
    if failed_operations:
        failures.append("cleanup_operations_failed")
    if stephanie_bad:
        failures.append("active_stephanie_record_still_says_fired")
    if greece_primary:
        failures.append("active_relocation_plan_still_uses_greece_as_primary")
    if orphan_milestones:
        failures.append("active_orphan_milestones_remain")
    if not app_plans:
        failures.append("active_app_plan_missing")
    if not relocation_plans:
        failures.append("active_relocation_plan_missing")
    if missing_relocation_milestones:
        failures.append("canonical_relocation_milestones_missing")
    if missing_app_milestones:
        failures.append("canonical_app_milestones_missing")
    if noisy_melissa:
        failures.append("active_melissa_milestones_remain")
    if noisy_first_million:
        failures.append("first_million_still_active_as_milestone")
    if wrong_app_names:
        failures.append("wrong_app_name_still_active_in_milestones")
    duplicate_commitments = _duplicate_commitment_groups(commitments)
    if duplicate_commitments:
        failures.append("duplicate_commitments_remain")

    return {
        "passed": not failures,
        "failures": failures,
        "active_plan_count": len(active_plans),
        "open_milestone_count": len(open_milestones),
        "open_commitment_count": len(
            [
                commitment
                for commitment in commitments
                if _active(commitment)
                and str(commitment.get("status") or "open") in {"open", "in_progress"}
            ]
        ),
        "active_plan_titles": [str(plan.get("title") or "") for plan in active_plans],
        "remaining_noisy_record_ids": {
            "stephanie": [entity.get("id") for entity in stephanie_bad],
            "greece_primary": [plan.get("id") for plan in greece_primary],
            "orphan_milestones": [milestone.get("id") for milestone in orphan_milestones],
            "melissa_milestones": [milestone.get("id") for milestone in noisy_melissa],
            "first_million": [milestone.get("id") for milestone in noisy_first_million],
            "wrong_app_names": [milestone.get("id") for milestone in wrong_app_names],
            "duplicate_commitments": [
                commitment.get("id")
                for group in duplicate_commitments.values()
                for commitment in group
            ],
            "missing_relocation_milestones": missing_relocation_milestones,
            "missing_app_milestones": missing_app_milestones,
            "failed_operations": [
                {
                    "action": item.get("action"),
                    "record_type": item.get("record_type"),
                    "record_id": item.get("record_id"),
                    "title": item.get("title"),
                    "error": item.get("error"),
                }
                for item in failed_operations
            ],
        },
    }


async def _apply_operations(
    memory_service: SupabaseMemoryService,
    operations: list[CleanupOperation],
) -> list[dict[str, Any]]:
    applied = []
    for operation in operations:
        try:
            result = await _apply_operation(memory_service, operation)
            applied.append(
                {
                    "action": operation.action,
                    "record_type": operation.record_type,
                    "record_id": operation.record_id,
                    "title": operation.title,
                    "success": bool(result),
                }
            )
        except Exception as error:  # pragma: no cover - CLI safety net
            applied.append(
                {
                    "action": operation.action,
                    "record_type": operation.record_type,
                    "record_id": operation.record_id,
                    "title": operation.title,
                    "success": False,
                    "error": str(error),
                }
            )
    return applied


async def _apply_operation(
    memory_service: SupabaseMemoryService,
    operation: CleanupOperation,
) -> Any:
    if operation.action == "create_plan":
        return await memory_service.create_plan(operation.updates)
    if operation.action == "create_plan_milestone":
        return await memory_service.create_plan_milestone(operation.updates)
    if not operation.record_id:
        return None
    if operation.record_type == "plan":
        return await memory_service.update_plan(operation.record_id, **operation.updates)
    if operation.record_type == "milestone":
        return await memory_service.update_plan_milestone(
            operation.record_id,
            **operation.updates,
        )
    if operation.record_type == "commitment":
        return await memory_service.update_commitment(
            operation.record_id,
            **operation.updates,
        )
    if operation.record_type == "entity":
        return await memory_service.update_entity(operation.record_id, **operation.updates)
    return None


def _create_app_plan_operation() -> CleanupOperation:
    return CleanupOperation(
        action="create_plan",
        record_type="plan",
        record_id=None,
        title=APP_PLAN_TITLE,
        reason="recreate canonical app launch plan after duplicate plan cleanup",
        updates={
            "plan_type": "career",
            "title": APP_PLAN_TITLE,
            "description": APP_PLAN_DESCRIPTION,
            "desired_outcome": APP_PLAN_OUTCOME,
            "priority": 5,
            "status": "active",
            "active": True,
            "metadata": {
                "rex_brain_v2_cleanup": True,
                "cleanup_version": CLEANUP_VERSION,
                "created_by_cleanup": True,
            },
        },
    )


def _update_plan_operation(
    plan: dict[str, Any],
    *,
    title: str,
    description: str,
    desired_outcome: str,
    reason: str,
) -> CleanupOperation:
    metadata = {
        **_metadata(plan),
        "rex_brain_v2_cleanup": True,
        "cleanup_version": CLEANUP_VERSION,
    }
    return CleanupOperation(
        action="update_plan",
        record_type="plan",
        record_id=str(plan.get("id") or ""),
        title=str(plan.get("title") or title),
        reason=reason,
        updates={
            "title": title,
            "description": description,
            "desired_outcome": desired_outcome,
            "metadata": metadata,
        },
    )


def _archive_plan_operation(
    plan: dict[str, Any],
    target: dict[str, Any] | None,
) -> CleanupOperation:
    metadata = {
        **_metadata(plan),
        "cleanup_reason": "rex_brain_v2_current_data_cleanup",
        "cleanup_version": CLEANUP_VERSION,
    }
    if target:
        metadata["consolidated_into_plan_id"] = target.get("id")
        metadata["consolidated_into_title"] = target.get("title")
    return CleanupOperation(
        action="archive_plan",
        record_type="plan",
        record_id=str(plan.get("id") or ""),
        title=str(plan.get("title") or "Plan"),
        reason="archive duplicate, stale, or exploratory top-level plan",
        updates={"active": False, "status": "archived", "metadata": metadata},
    )


def _canonical_milestone_operations(
    *,
    milestones: list[dict[str, Any]],
    plan: dict[str, Any],
    canonical: list[tuple[str, str]],
    reason: str,
) -> list[CleanupOperation]:
    operations = []
    plan_id = str(plan.get("id") or "")
    existing = [milestone for milestone in milestones if milestone.get("plan_id") == plan_id]
    for title, description in canonical:
        match = _best_milestone_match(existing, title)
        payload = {
            "plan_id": plan_id,
            "title": title,
            "description": description,
            "milestone_type": "checkpoint",
            "priority": 5,
            "status": "open",
            "active": True,
            "metadata": {
                **_metadata(match or {}),
                "rex_brain_v2_cleanup": True,
                "cleanup_version": CLEANUP_VERSION,
                "achievement_milestone": True,
            },
        }
        if match:
            operations.append(
                CleanupOperation(
                    action="update_plan_milestone",
                    record_type="milestone",
                    record_id=str(match.get("id") or ""),
                    title=str(match.get("title") or title),
                    reason=reason,
                    updates=payload,
                )
            )
        else:
            operations.append(
                CleanupOperation(
                    action="create_plan_milestone",
                    record_type="milestone",
                    record_id=None,
                    title=title,
                    reason=reason,
                    updates=payload,
                )
            )
    return operations


def _archive_noisy_milestones(
    *,
    milestones: list[dict[str, Any]],
    plan: dict[str, Any],
    keep_titles: set[str],
    keep_ids: set[str] | None = None,
    matcher: Any,
) -> list[CleanupOperation]:
    operations = []
    plan_id = str(plan.get("id") or "")
    normalized_keep = {_normalize(title) for title in keep_titles}
    protected_ids = keep_ids or set()
    for milestone in milestones:
        if milestone.get("plan_id") != plan_id or not _active(milestone):
            continue
        if str(milestone.get("id") or "") in protected_ids:
            continue
        title = str(milestone.get("title") or "")
        if _normalize(title) in normalized_keep:
            continue
        if matcher(milestone):
            operations.append(_archive_milestone_operation(milestone))
    return operations


def _archive_milestone_operation(
    milestone: dict[str, Any],
    *,
    cleanup_reason: str = "rex_brain_v2_noisy_or_duplicate_milestone",
    reason: str = "archive noisy duplicate milestone or chat fragment",
) -> CleanupOperation:
    metadata = {
        **_metadata(milestone),
        "cleanup_reason": cleanup_reason,
        "cleanup_version": CLEANUP_VERSION,
    }
    return CleanupOperation(
        action="archive_plan_milestone",
        record_type="milestone",
        record_id=str(milestone.get("id") or ""),
        title=str(milestone.get("title") or "Milestone"),
        reason=reason,
        updates={"active": False, "status": "canceled", "metadata": metadata},
    )


def _entity_correction_operations(entities: list[dict[str, Any]]) -> list[CleanupOperation]:
    operations = []
    for entity in entities:
        text = _entity_text(entity)
        identity = _entity_identity_text(entity)
        display = str(entity.get("display_name") or "")
        if re.search(r"\b(laura|lara)\b", identity):
            aliases = _aliases_with(entity, {"Lara", "Laura"})
            operations.append(
                CleanupOperation(
                    action="update_entity",
                    record_type="entity",
                    record_id=str(entity.get("id") or ""),
                    title=display or "Lara",
                    reason="correct Lara/Laura fired fact",
                    updates={
                        "display_name": display or "Lara",
                        "aliases": aliases,
                        "relationship": "kitchen supervisor user dated last year",
                        "summary": (
                            "Kitchen supervisor the user dated last year; "
                            "got fired at the beginning of this year."
                        ),
                        "metadata": {
                            **_metadata(entity),
                            "cleanup_version": CLEANUP_VERSION,
                            "fact_verified_by_user": True,
                        },
                    },
                )
            )
        if "stephanie" in identity:
            operations.append(
                CleanupOperation(
                    action="update_entity",
                    record_type="entity",
                    record_id=str(entity.get("id") or ""),
                    title=display or "Stephanie",
                    reason="remove incorrect Stephanie fired fact",
                    updates={
                        "display_name": display or "Stephanie",
                        "relationship": "Lara's friend who lives with her",
                        "summary": (
                            "Lara's friend who lives with her; quit about a "
                            "month ago. Stephanie was not fired at the "
                            "beginning of this year."
                        ),
                        "metadata": {
                            **_metadata(entity),
                            "cleanup_version": CLEANUP_VERSION,
                            "fact_verified_by_user": True,
                        },
                    },
                )
            )
    return operations


def _orphan_commitment_operations(
    commitments: list[dict[str, Any]],
    plan_by_id: dict[str, dict[str, Any]],
) -> list[CleanupOperation]:
    operations = []
    for commitment in commitments:
        plan_id = str(commitment.get("plan_id") or "")
        if not plan_id or plan_id in plan_by_id or not _active(commitment):
            continue
        operations.append(
            CleanupOperation(
                action="archive_commitment",
                record_type="commitment",
                record_id=str(commitment.get("id") or ""),
                title=str(commitment.get("title") or "Commitment"),
                reason="archive commitment linked to inactive or missing plan",
                updates={
                    "active": False,
                    "status": "archived",
                    "metadata": {
                        **_metadata(commitment),
                        "cleanup_version": CLEANUP_VERSION,
                        "cleanup_reason": "orphaned_commitment",
                    },
                },
            )
        )
    return operations


def _duplicate_commitment_operations(
    commitments: list[dict[str, Any]],
) -> list[CleanupOperation]:
    operations = []
    for group in _duplicate_commitment_groups(commitments).values():
        keep = _best_commitment(group)
        for commitment in group:
            if commitment is keep:
                continue
            operations.append(
                CleanupOperation(
                    action="archive_commitment",
                    record_type="commitment",
                    record_id=str(commitment.get("id") or ""),
                    title=str(commitment.get("title") or "Commitment"),
                    reason="archive duplicate open commitment",
                    updates={
                        "active": False,
                        "status": "archived",
                        "metadata": {
                            **_metadata(commitment),
                            "cleanup_version": CLEANUP_VERSION,
                            "cleanup_reason": "duplicate_commitment",
                            "consolidated_into_commitment_id": keep.get("id"),
                            "consolidated_into_title": keep.get("title"),
                        },
                    },
                )
            )
    return operations


def _duplicate_commitment_groups(
    commitments: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for commitment in commitments:
        if not _active(commitment):
            continue
        status = str(commitment.get("status") or "open")
        if status not in {"open", "in_progress"}:
            continue
        key = _semantic_commitment_key(commitment)
        if not key:
            continue
        groups.setdefault(key, []).append(commitment)
    return {key: group for key, group in groups.items() if len(group) > 1}


def _best_commitment(group: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        group,
        key=lambda commitment: (
            int(commitment.get("priority") or 3),
            str(commitment.get("updated_at") or commitment.get("created_at") or ""),
        ),
    )


def _orphan_milestone_operations(
    milestones: list[dict[str, Any]],
    plan_by_id: dict[str, dict[str, Any]],
) -> list[CleanupOperation]:
    operations = []
    for milestone in milestones:
        plan_id = str(milestone.get("plan_id") or "")
        if not _active(milestone) or plan_id in plan_by_id:
            continue
        operations.append(
            _archive_milestone_operation(
                milestone,
                cleanup_reason="orphaned_milestone",
                reason="archive milestone linked to inactive or missing parent plan",
            )
        )
    return operations


def _target_plan_for_archive(
    plan: dict[str, Any],
    relocation_plan: dict[str, Any] | None,
    app_plan: dict[str, Any] | None,
    melissa_plan: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if _is_melissa_plan(plan):
        return melissa_plan
    if _is_app_plan(plan):
        return app_plan
    if _is_relocation_plan(plan):
        return relocation_plan
    return None


def _should_archive_plan(plan: dict[str, Any]) -> bool:
    text = _record_text(plan)
    if "launch rex melissa" in text:
        return True
    if "first million" in text:
        return True
    if _is_relocation_plan(plan):
        return True
    if _is_app_plan(plan):
        return True
    if _is_melissa_plan(plan):
        return True
    return False


def _is_relocation_plan(plan: dict[str, Any]) -> bool:
    text = _record_text(plan)
    tokens = set(re.findall(r"[a-z0-9$]+", text))
    return bool(
        tokens
        & {
            "abroad",
            "citizenship",
            "d7",
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
            "visa",
        }
    )


def _is_app_plan(plan: dict[str, Any]) -> bool:
    text = _record_text(plan)
    tokens = set(re.findall(r"[a-z0-9$]+", text))
    return len(tokens & {"app", "apps", "clarity", "echodesk", "flowforce", "rex"}) >= 2


def _is_melissa_plan(plan: dict[str, Any]) -> bool:
    return "melissa" in _record_text(plan)


def _is_noisy_relocation_milestone(milestone: dict[str, Any]) -> bool:
    text = _record_text(milestone)
    if "first million" in text:
        return True
    return any(
        phrase in text
        for phrase in (
            "europe move",
            "europe relocation via",
            "european relocation via",
            "relocate to europe",
            "relocation to portugal",
            "digital nomad visa",
            "move out of the country",
            "international relocation",
            "income generation and europe relocation",
            "eu business setup",
            "estonia e-residency",
            "estonia e residency",
            "italian ancestry residency",
            "relocating abroad from the usa",
            "one-year location-independent income",
            "one year location independent income",
            "minimum monthly income",
            "monthly savings",
            "client acquisition",
            "increase income via freelance",
            "$5k monthly revenue",
            "reach 5k monthly income",
            "reach $600 monthly savings",
        )
    )


def _is_noisy_app_milestone(milestone: dict[str, Any]) -> bool:
    text = _record_text(milestone)
    return any(
        phrase in text
        for phrase in (
            "launch rex melissa",
            "three-month app development",
            "three month app development",
            "rex ai assistant",
            "3-month app development push",
            "3 month app development push",
            "project sequence",
            "monetize multi-user rex",
            "monetize multi user rex",
            "launch three apps",
            "build and launch flowforce app",
            "ecodesk",
            "flow force",
        )
    )


def _is_melissa_milestone(milestone: dict[str, Any]) -> bool:
    return "melissa" in _record_text(milestone)


def _semantic_commitment_key(commitment: dict[str, Any]) -> str | None:
    text = _record_text(commitment)
    tokens = set(text.split())
    if tokens & {"saving", "savings", "save"} and (
        tokens & {"automatic", "auto", "paycheck", "transfer", "transferred"}
    ):
        return "automatic_savings"
    if tokens & {"weekly", "shipping", "ship", "release", "releases"}:
        return "weekly_shipping"
    if tokens & {"greek", "practice"}:
        return "greek_practice"
    return None


def _operation_record_ids(operations: list[CleanupOperation]) -> set[str]:
    return {str(operation.record_id) for operation in operations if operation.record_id}


def _has_app_evidence(
    *,
    plans: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
) -> bool:
    records = [*plans, *milestones]
    return any(
        _is_app_plan(record) or _is_noisy_app_milestone(record)
        for record in records
    )


def _select_plan(plans: list[dict[str, Any]], matcher: Any) -> dict[str, Any] | None:
    matches = [plan for plan in plans if _active(plan) and matcher(plan)]
    if not matches:
        return None
    return max(
        matches,
        key=lambda plan: (
            _specificity_score(plan),
            int(plan.get("priority") or 3),
            str(plan.get("updated_at") or plan.get("created_at") or ""),
        ),
    )


def _specificity_score(plan: dict[str, Any]) -> int:
    text = _record_text(plan)
    score = 0
    if "relocate to greece" in text:
        score += 5
    if "three-month app development" in text:
        score += 5
    if "ask melissa" in text:
        score += 5
    if plan.get("description"):
        score += 1
    return score


def _best_milestone_match(
    milestones: list[dict[str, Any]],
    canonical_title: str,
) -> dict[str, Any] | None:
    canonical_key = _semantic_milestone_key(canonical_title)
    matches = [
        milestone
        for milestone in milestones
        if _semantic_milestone_key(str(milestone.get("title") or ""))
        == canonical_key
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda milestone: (
            _active(milestone),
            int(milestone.get("priority") or 3),
            str(milestone.get("updated_at") or milestone.get("created_at") or ""),
        ),
    )


def _semantic_milestone_key(title: str) -> str:
    text = _normalize(title)
    tokens = set(text.split())
    if tokens & {"italian", "citizenship", "eligibility"}:
        return "italian_citizenship"
    if tokens & {"portugal", "d7", "nomad", "backup"}:
        return "portugal_backup"
    if "3k" in tokens or "3000" in tokens:
        return "income_3k"
    if "5k" in tokens or "5000" in tokens:
        return "income_5k"
    if "clarity" in tokens:
        return "clarity_launch"
    if "echodesk" in tokens or "ecodesk" in tokens:
        return "echodesk_launch"
    if "flowforce" in tokens or {"flow", "force"} <= tokens:
        return "flowforce_launch"
    if tokens & {"revenue", "subscription", "client"}:
        return "first_revenue"
    return text


def _missing_canonical_milestones(
    milestones: list[dict[str, Any]],
    plan: dict[str, Any] | None,
    canonical: list[tuple[str, str]],
) -> list[str]:
    if not plan:
        return [title for title, _ in canonical]
    plan_id = str(plan.get("id") or "")
    active_titles = {
        _normalize(str(milestone.get("title") or ""))
        for milestone in milestones
        if _active(milestone)
        and str(milestone.get("status") or "open") in {"open", "in_progress"}
        and str(milestone.get("plan_id") or "") == plan_id
    }
    return [
        title
        for title, _ in canonical
        if _normalize(title) not in active_titles
    ]


def _dedupe_operations(operations: list[CleanupOperation]) -> list[CleanupOperation]:
    seen: set[tuple[str, str, str | None]] = set()
    deduped = []
    for operation in operations:
        record_key = operation.record_id or operation.title
        key = (operation.action, operation.record_type, record_key)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(operation)
    return deduped


def _aliases_with(entity: dict[str, Any], names: set[str]) -> list[str]:
    aliases = entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
    normalized = {str(alias).casefold() for alias in aliases}
    result = [str(alias) for alias in aliases]
    for name in sorted(names):
        if name.casefold() not in normalized:
            result.append(name)
    return result


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _active(record: dict[str, Any]) -> bool:
    return record.get("active") is not False and str(record.get("status") or "active") not in {
        "archived",
        "canceled",
        "completed",
        "inactive",
    }


def _entity_text(entity: dict[str, Any]) -> str:
    aliases = entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
    return _normalize(
        " ".join(
            [
                str(entity.get("display_name") or ""),
                str(entity.get("normalized_name") or ""),
                str(entity.get("relationship") or ""),
                str(entity.get("summary") or ""),
                " ".join(str(alias) for alias in aliases),
            ]
        )
    )


def _entity_identity_text(entity: dict[str, Any]) -> str:
    aliases = entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
    return _normalize(
        " ".join(
            [
                str(entity.get("display_name") or ""),
                str(entity.get("normalized_name") or ""),
                " ".join(str(alias) for alias in aliases),
            ]
        )
    )


def _record_text(record: dict[str, Any]) -> str:
    return _normalize(
        " ".join(
            str(record.get(field) or "")
            for field in (
                "title",
                "description",
                "desired_outcome",
                "commitment_text",
                "summary",
                "relationship",
            )
        )
    )


def _normalize(value: Any) -> str:
    cleaned = re.sub(r"[^a-z0-9$]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean current production Rex Brain v2 data after safeguards exist."
    )
    parser.add_argument("--apply", action="store_true", help="Apply cleanup writes.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview cleanup writes without applying them. This is the default.",
    )
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    await startup_http_client()
    try:
        report = await cleanup_rex_brain_v2_current_data(
            SupabaseMemoryService(),
            apply=args.apply,
            limit=args.limit,
        )
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    finally:
        await shutdown_http_client()


if __name__ == "__main__":
    asyncio.run(_main())
