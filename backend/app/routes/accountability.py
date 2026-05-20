import asyncio
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.dependencies import get_accountability_service, get_memory_service
from app.models.accountability import (
    AccountabilityOverviewResponse,
    AccountabilitySeverity,
    AccountabilitySignalResponse,
    AccountabilitySignalType,
    AccountabilitySourceType,
    AccountabilityStatus,
)
from app.services.accountability_service import AccountabilityService
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService
from app.services.time_context_service import TimeContextService


router = APIRouter(prefix="/accountability", tags=["accountability"])

DEFAULT_ACCOUNTABILITY_MESSAGE = "Review my current accountability context."
ACCOUNTABILITY_CONTEXT_LIMIT = 50


@router.get("/signals", response_model=list[AccountabilitySignalResponse])
async def list_accountability_signals(
    message: str = Query(default=DEFAULT_ACCOUNTABILITY_MESSAGE, min_length=1),
    signal_type: Optional[AccountabilitySignalType] = Query(default=None),
    severity: Optional[AccountabilitySeverity] = Query(default=None),
    status: Optional[AccountabilityStatus] = Query(default="active"),
    source_type: Optional[AccountabilitySourceType] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
    accountability_service: AccountabilityService = Depends(get_accountability_service),
) -> list[AccountabilitySignalResponse]:
    context = await _load_accountability_context(memory_service, message)
    signals = await _analyze_signals(accountability_service, message, context)
    return _filter_signals(
        signals,
        signal_type=signal_type,
        severity=severity,
        status=status,
        source_type=source_type,
        limit=limit,
    )


@router.get("/rule-risks", response_model=list[AccountabilitySignalResponse])
async def list_rule_risks(
    message: str = Query(default=DEFAULT_ACCOUNTABILITY_MESSAGE, min_length=1),
    severity: Optional[AccountabilitySeverity] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
    accountability_service: AccountabilityService = Depends(get_accountability_service),
) -> list[AccountabilitySignalResponse]:
    context = await _load_accountability_context(memory_service, message)
    signals = await _analyze_signals(accountability_service, message, context)
    return _filter_signals(
        signals,
        signal_type="rule_violation",
        severity=severity,
        status="active",
        source_type=None,
        limit=limit,
    )


@router.get("/plan-risks", response_model=list[AccountabilitySignalResponse])
async def list_plan_risks(
    message: str = Query(default=DEFAULT_ACCOUNTABILITY_MESSAGE, min_length=1),
    severity: Optional[AccountabilitySeverity] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
    accountability_service: AccountabilityService = Depends(get_accountability_service),
) -> list[AccountabilitySignalResponse]:
    context = await _load_accountability_context(memory_service, message)
    signals = await _analyze_signals(accountability_service, message, context)
    filtered = [
        signal
        for signal in signals
        if signal.signal_type in {"plan_drift", "upcoming_deadline"}
    ]
    return _filter_signals(
        filtered,
        signal_type=None,
        severity=severity,
        status="active",
        source_type=None,
        limit=limit,
    )


@router.get("/patterns", response_model=list[AccountabilitySignalResponse])
async def list_recent_patterns(
    message: str = Query(default=DEFAULT_ACCOUNTABILITY_MESSAGE, min_length=1),
    severity: Optional[AccountabilitySeverity] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
    accountability_service: AccountabilityService = Depends(get_accountability_service),
) -> list[AccountabilitySignalResponse]:
    context = await _load_accountability_context(memory_service, message)
    signals = await _analyze_signals(accountability_service, message, context)
    return _filter_signals(
        signals,
        signal_type="repeated_pattern",
        severity=severity,
        status="active",
        source_type=None,
        limit=limit,
    )


@router.get("/overview", response_model=AccountabilityOverviewResponse)
async def accountability_overview(
    message: str = Query(default=DEFAULT_ACCOUNTABILITY_MESSAGE, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
    accountability_service: AccountabilityService = Depends(get_accountability_service),
) -> AccountabilityOverviewResponse:
    context = await _load_accountability_context(memory_service, message)
    signals = await _analyze_signals(accountability_service, message, context)
    active_signals = _filter_signals(
        signals,
        signal_type=None,
        severity=None,
        status="active",
        source_type=None,
        limit=limit,
    )
    rule_risks = [
        signal for signal in active_signals if signal.signal_type == "rule_violation"
    ]
    plan_risks = [
        signal
        for signal in active_signals
        if signal.signal_type in {"plan_drift", "upcoming_deadline"}
    ]
    recent_patterns = [
        signal for signal in active_signals if signal.signal_type == "repeated_pattern"
    ]
    open_commitments = _open_commitments(context["commitments"])
    open_milestones = _open_milestones(context["plan_milestones"])
    plan_hierarchy = _plan_hierarchy(
        plans=context["plans"],
        milestones=open_milestones,
        commitments=open_commitments,
    )
    duplicate_warnings = _duplicate_warnings(
        plans=context["plans"],
        rules=context["personal_rules"],
    )

    return AccountabilityOverviewResponse(
        signals=active_signals,
        rule_risks=rule_risks,
        plan_risks=plan_risks,
        recent_patterns=recent_patterns,
        active_rules=context["personal_rules"],
        open_commitments=open_commitments,
        active_plans=context["plans"],
        open_milestones=open_milestones,
        plan_hierarchy=plan_hierarchy,
        duplicate_warnings=duplicate_warnings,
        metadata={
            "message": message,
            "signal_count": len(active_signals),
            "active_rule_count": len(context["personal_rules"]),
            "open_commitment_count": len(open_commitments),
            "active_plan_count": len(context["plans"]),
            "open_milestone_count": len(open_milestones),
            "open_task_count": len(open_commitments),
            "duplicate_warning_count": len(duplicate_warnings),
        },
    )


async def _load_accountability_context(
    memory_service: SupabaseMemoryService,
    message: str,
) -> dict:
    try:
        (
            personal_rules,
            commitments,
            plans,
            plan_milestones,
            entity_events,
            relevant_memories,
        ) = await asyncio.gather(
            memory_service.list_personal_rules(
                active=True,
                status="active",
                limit=ACCOUNTABILITY_CONTEXT_LIMIT,
            ),
            memory_service.list_commitments(
                active=True,
                limit=ACCOUNTABILITY_CONTEXT_LIMIT,
            ),
            memory_service.list_plans(
                active=True,
                status="active",
                limit=ACCOUNTABILITY_CONTEXT_LIMIT,
            ),
            memory_service.list_plan_milestones(
                active=True,
                limit=ACCOUNTABILITY_CONTEXT_LIMIT,
            ),
            memory_service.list_entity_events(
                active=True,
                limit=ACCOUNTABILITY_CONTEXT_LIMIT,
            ),
            memory_service.get_relevant_memories(
                query=message,
                limit=ACCOUNTABILITY_CONTEXT_LIMIT,
            ),
        )
    except MemoryServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    return {
        "personal_rules": personal_rules,
        "commitments": commitments,
        "plans": plans,
        "plan_milestones": plan_milestones,
        "entity_events": entity_events,
        "relevant_memories": relevant_memories,
        "time_context": TimeContextService(
            timezone_name=get_settings().app_timezone,
        ).current_context(),
    }


async def _analyze_signals(
    accountability_service: AccountabilityService,
    message: str,
    context: dict,
) -> list[AccountabilitySignalResponse]:
    try:
        signals = await accountability_service.analyze_signals(
            message=message,
            time_context=context["time_context"],
            personal_rules=context["personal_rules"],
            commitments=context["commitments"],
            plans=context["plans"],
            plan_milestones=context["plan_milestones"],
            entity_events=context["entity_events"],
            relevant_memories=context["relevant_memories"],
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Accountability analysis failed.",
        ) from error

    return [AccountabilitySignalResponse(**signal.model_dump()) for signal in signals]


def _filter_signals(
    signals: list[AccountabilitySignalResponse],
    *,
    signal_type: Optional[AccountabilitySignalType],
    severity: Optional[AccountabilitySeverity],
    status: Optional[AccountabilityStatus],
    source_type: Optional[AccountabilitySourceType],
    limit: int,
) -> list[AccountabilitySignalResponse]:
    filtered = []
    for signal in signals:
        if signal_type is not None and signal.signal_type != signal_type:
            continue
        if severity is not None and signal.severity != severity:
            continue
        if status is not None and signal.status != status:
            continue
        if source_type is not None and not any(
            source.source_type == source_type for source in signal.source_refs
        ):
            continue
        filtered.append(signal)
    return filtered[:limit]


def _open_commitments(commitments: list[dict]) -> list[dict]:
    return [
        commitment
        for commitment in commitments
        if commitment.get("active") is not False
        and commitment.get("status", "open") in {"open", "in_progress"}
    ]


def _open_milestones(milestones: list[dict]) -> list[dict]:
    return [
        milestone
        for milestone in milestones
        if milestone.get("active") is not False
        and milestone.get("status", "open") in {"open", "in_progress"}
    ]


def _plan_hierarchy(
    *,
    plans: list[dict],
    milestones: list[dict],
    commitments: list[dict],
) -> list[dict]:
    milestones_by_plan: dict[str, list[dict]] = {}
    commitments_by_plan: dict[str, list[dict]] = {}
    commitments_by_milestone: dict[str, list[dict]] = {}

    for milestone in milestones:
        plan_id = str(milestone.get("plan_id") or "")
        if plan_id:
            milestones_by_plan.setdefault(plan_id, []).append(milestone)

    for commitment in commitments:
        milestone_id = str(commitment.get("milestone_id") or "")
        plan_id = str(commitment.get("plan_id") or "")
        if milestone_id:
            commitments_by_milestone.setdefault(milestone_id, []).append(commitment)
        elif plan_id:
            commitments_by_plan.setdefault(plan_id, []).append(commitment)

    hierarchy = []
    for plan in plans:
        plan_id = str(plan.get("id") or "")
        plan_milestones = []
        for milestone in milestones_by_plan.get(plan_id, []):
            milestone_id = str(milestone.get("id") or "")
            plan_milestones.append(
                {
                    **milestone,
                    "open_commitments": commitments_by_milestone.get(
                        milestone_id,
                        [],
                    ),
                }
            )

        hierarchy.append(
            {
                "plan": plan,
                "open_milestones": plan_milestones,
                "open_commitments": commitments_by_plan.get(plan_id, []),
                "counts": {
                    "open_milestones": len(plan_milestones),
                    "open_commitments": len(commitments_by_plan.get(plan_id, []))
                    + sum(
                        len(item.get("open_commitments") or [])
                        for item in plan_milestones
                    ),
                },
            }
        )
    return hierarchy


def _duplicate_warnings(
    *,
    plans: list[dict],
    rules: list[dict],
) -> list[dict]:
    warnings = []
    warnings.extend(
        _duplicate_warning_group(
            records=plans,
            record_type="plan",
            title_field="title",
            text_fields=("title", "description", "desired_outcome"),
        )
    )
    warnings.extend(
        _duplicate_warning_group(
            records=rules,
            record_type="rule",
            title_field="title",
            text_fields=("title", "rule_text"),
        )
    )
    return warnings


def _duplicate_warning_group(
    *,
    records: list[dict],
    record_type: str,
    title_field: str,
    text_fields: tuple[str, ...],
) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for record in records:
        if record.get("active") is False:
            continue
        key = _duplicate_key(record, text_fields)
        if not key:
            continue
        groups.setdefault(key, []).append(record)

    warnings = []
    for group in groups.values():
        if len(group) < 2:
            continue
        warnings.append(
            {
                "record_type": record_type,
                "title": str(group[0].get(title_field) or record_type),
                "record_ids": [str(record.get("id")) for record in group if record.get("id")],
                "reason": "multiple_active_records_share_core_wording",
            }
        )
    return warnings


def _duplicate_key(record: dict, fields: tuple[str, ...]) -> str:
    parts = [str(record.get(field) or "") for field in fields]
    text = " ".join(parts).casefold()
    tokens = [
        token
        for token in re.findall(r"[a-z0-9$]+", text)
        if len(token) > 2
        and token
        not in {
            "active",
            "and",
            "for",
            "from",
            "goal",
            "plan",
            "the",
            "this",
            "with",
        }
    ]
    return " ".join(tokens[:8])
