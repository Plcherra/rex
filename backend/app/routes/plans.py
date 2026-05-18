from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import get_plan_service
from app.models.plan import (
    MilestoneStatus,
    PlanCreateRequest,
    PlanMilestoneCreateRequest,
    PlanMilestoneResponse,
    PlanMilestoneUpdateRequest,
    PlanResponse,
    PlanStatus,
    PlanType,
    PlanUpdateRequest,
)
from app.services.plan_service import PlanService, PlanServiceError


router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse])
async def list_plans(
    plan_type: Optional[PlanType] = Query(default=None),
    status: Optional[PlanStatus] = Query(default=None),
    active: Optional[bool] = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    plan_service: PlanService = Depends(get_plan_service),
) -> list[PlanResponse]:
    try:
        plans = await plan_service.list_plans(
            plan_type=plan_type,
            status=status,
            active=active,
            limit=limit,
        )
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return [PlanResponse(**plan) for plan in plans]


@router.post("", response_model=PlanResponse, status_code=201)
async def create_plan(
    request: PlanCreateRequest,
    plan_service: PlanService = Depends(get_plan_service),
) -> PlanResponse:
    try:
        plan = await plan_service.create_plan(request)
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return PlanResponse(**plan)


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: str,
    request: PlanUpdateRequest,
    plan_service: PlanService = Depends(get_plan_service),
) -> PlanResponse:
    try:
        plan = await plan_service.update_plan(plan_id, request)
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return PlanResponse(**plan)


@router.delete("/{plan_id}", status_code=204)
async def deactivate_plan(
    plan_id: str,
    plan_service: PlanService = Depends(get_plan_service),
) -> Response:
    try:
        await plan_service.deactivate_plan(plan_id)
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return Response(status_code=204)


@router.get("/{plan_id}/milestones", response_model=list[PlanMilestoneResponse])
async def list_milestones(
    plan_id: str,
    status: Optional[MilestoneStatus] = Query(default=None),
    active: Optional[bool] = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    plan_service: PlanService = Depends(get_plan_service),
) -> list[PlanMilestoneResponse]:
    try:
        milestones = await plan_service.list_milestones(
            plan_id=plan_id,
            status=status,
            active=active,
            limit=limit,
        )
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return [PlanMilestoneResponse(**milestone) for milestone in milestones]


@router.post("/{plan_id}/milestones", response_model=PlanMilestoneResponse, status_code=201)
async def create_milestone(
    plan_id: str,
    request: PlanMilestoneCreateRequest,
    plan_service: PlanService = Depends(get_plan_service),
) -> PlanMilestoneResponse:
    if request.plan_id != plan_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Plan ID mismatch.")

    try:
        milestone = await plan_service.create_milestone(request)
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return PlanMilestoneResponse(**milestone)


@router.patch("/milestones/{milestone_id}", response_model=PlanMilestoneResponse)
async def update_milestone(
    milestone_id: str,
    request: PlanMilestoneUpdateRequest,
    plan_service: PlanService = Depends(get_plan_service),
) -> PlanMilestoneResponse:
    try:
        milestone = await plan_service.update_milestone(milestone_id, request)
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return PlanMilestoneResponse(**milestone)


@router.delete("/milestones/{milestone_id}", status_code=204)
async def deactivate_milestone(
    milestone_id: str,
    plan_service: PlanService = Depends(get_plan_service),
) -> Response:
    try:
        await plan_service.deactivate_milestone(milestone_id)
    except PlanServiceError as error:
        raise _plan_http_error(error) from error

    return Response(status_code=204)


def _plan_http_error(error: PlanServiceError):
    from fastapi import HTTPException

    return HTTPException(status_code=error.status_code, detail=error.detail)
