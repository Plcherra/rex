import asyncio
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

    return AccountabilityOverviewResponse(
        signals=active_signals,
        rule_risks=rule_risks,
        plan_risks=plan_risks,
        recent_patterns=recent_patterns,
        active_rules=context["personal_rules"],
        open_commitments=_open_commitments(context["commitments"]),
        active_plans=context["plans"],
        open_milestones=_open_milestones(context["plan_milestones"]),
        metadata={
            "message": message,
            "signal_count": len(active_signals),
            "active_rule_count": len(context["personal_rules"]),
            "open_commitment_count": len(_open_commitments(context["commitments"])),
            "active_plan_count": len(context["plans"]),
            "open_milestone_count": len(_open_milestones(context["plan_milestones"])),
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
