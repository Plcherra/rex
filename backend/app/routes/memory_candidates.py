from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_memory_candidate_service
from app.models.memory_candidate import (
    MemoryCandidateApproveRequest,
    MemoryCandidateBulkDecisionRequest,
    MemoryCandidateBulkDecisionResponse,
    MemoryCandidateCreateRequest,
    MemoryCandidateRejectRequest,
    MemoryCandidateResponse,
    MemoryCandidateRiskLevel,
    MemoryCandidateStatus,
    MemoryCandidateType,
    MemoryCandidateUpdateRequest,
)
from app.services.memory_candidate_service import (
    MemoryCandidateService,
    MemoryCandidateServiceError,
)


router = APIRouter(prefix="/memory-candidates", tags=["memory-candidates"])


@router.get("", response_model=list[MemoryCandidateResponse])
async def list_memory_candidates(
    candidate_type: Optional[MemoryCandidateType] = Query(default=None),
    status: Optional[MemoryCandidateStatus] = Query(default=None),
    risk_level: Optional[MemoryCandidateRiskLevel] = Query(default=None),
    source_conversation_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    service: MemoryCandidateService = Depends(get_memory_candidate_service),
) -> list[MemoryCandidateResponse]:
    try:
        candidates = await service.list_candidates(
            candidate_type=candidate_type,
            status=status,
            risk_level=risk_level,
            source_conversation_id=source_conversation_id,
            limit=limit,
        )
    except MemoryCandidateServiceError as error:
        raise _candidate_http_error(error) from error
    return [MemoryCandidateResponse(**candidate) for candidate in candidates]


@router.post("", response_model=MemoryCandidateResponse, status_code=201)
async def create_memory_candidate(
    request: MemoryCandidateCreateRequest,
    service: MemoryCandidateService = Depends(get_memory_candidate_service),
) -> MemoryCandidateResponse:
    try:
        candidate = await service.create_candidate(request)
    except MemoryCandidateServiceError as error:
        raise _candidate_http_error(error) from error
    return MemoryCandidateResponse(**candidate)


@router.patch("/{candidate_id}", response_model=MemoryCandidateResponse)
async def update_memory_candidate(
    candidate_id: str,
    request: MemoryCandidateUpdateRequest,
    service: MemoryCandidateService = Depends(get_memory_candidate_service),
) -> MemoryCandidateResponse:
    try:
        candidate = await service.update_candidate(candidate_id, request)
    except MemoryCandidateServiceError as error:
        raise _candidate_http_error(error) from error
    return MemoryCandidateResponse(**candidate)


@router.post("/{candidate_id}/approve", response_model=MemoryCandidateResponse)
async def approve_memory_candidate(
    candidate_id: str,
    request: Optional[MemoryCandidateApproveRequest] = None,
    service: MemoryCandidateService = Depends(get_memory_candidate_service),
) -> MemoryCandidateResponse:
    try:
        candidate = await service.approve_candidate(
            candidate_id,
            request or MemoryCandidateApproveRequest(),
        )
    except MemoryCandidateServiceError as error:
        raise _candidate_http_error(error) from error
    return MemoryCandidateResponse(**candidate)


@router.post("/{candidate_id}/reject", response_model=MemoryCandidateResponse)
async def reject_memory_candidate(
    candidate_id: str,
    request: Optional[MemoryCandidateRejectRequest] = None,
    service: MemoryCandidateService = Depends(get_memory_candidate_service),
) -> MemoryCandidateResponse:
    try:
        candidate = await service.reject_candidate(
            candidate_id,
            request or MemoryCandidateRejectRequest(),
        )
    except MemoryCandidateServiceError as error:
        raise _candidate_http_error(error) from error
    return MemoryCandidateResponse(**candidate)


@router.post("/approve-all", response_model=MemoryCandidateBulkDecisionResponse)
async def approve_all_memory_candidates(
    request: MemoryCandidateBulkDecisionRequest,
    service: MemoryCandidateService = Depends(get_memory_candidate_service),
) -> MemoryCandidateBulkDecisionResponse:
    try:
        result = await service.bulk_approve_candidates(request)
    except MemoryCandidateServiceError as error:
        raise _candidate_http_error(error) from error
    return MemoryCandidateBulkDecisionResponse(**result)


@router.post("/reject-all", response_model=MemoryCandidateBulkDecisionResponse)
async def reject_all_memory_candidates(
    request: MemoryCandidateBulkDecisionRequest,
    service: MemoryCandidateService = Depends(get_memory_candidate_service),
) -> MemoryCandidateBulkDecisionResponse:
    try:
        result = await service.bulk_reject_candidates(request)
    except MemoryCandidateServiceError as error:
        raise _candidate_http_error(error) from error
    return MemoryCandidateBulkDecisionResponse(**result)


def _candidate_http_error(error: MemoryCandidateServiceError):
    from fastapi import HTTPException

    return HTTPException(status_code=error.status_code, detail=error.detail)
