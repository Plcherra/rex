from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import get_commitment_service
from app.models.commitment import (
    CommitmentCreateRequest,
    CommitmentResponse,
    CommitmentStatus,
    CommitmentType,
    CommitmentUpdateRequest,
)
from app.services.commitment_service import CommitmentService, CommitmentServiceError


router = APIRouter(prefix="/commitments", tags=["commitments"])


@router.get("", response_model=list[CommitmentResponse])
async def list_commitments(
    commitment_type: Optional[CommitmentType] = Query(default=None),
    milestone_id: Optional[str] = Query(default=None),
    status: Optional[CommitmentStatus] = Query(default=None),
    active: Optional[bool] = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    commitment_service: CommitmentService = Depends(get_commitment_service),
) -> list[CommitmentResponse]:
    try:
        commitments = await commitment_service.list_commitments(
            commitment_type=commitment_type,
            milestone_id=milestone_id,
            status=status,
            active=active,
            limit=limit,
        )
    except CommitmentServiceError as error:
        raise _commitment_http_error(error) from error

    return [CommitmentResponse(**commitment) for commitment in commitments]


@router.post("", response_model=CommitmentResponse, status_code=201)
async def create_commitment(
    request: CommitmentCreateRequest,
    commitment_service: CommitmentService = Depends(get_commitment_service),
) -> CommitmentResponse:
    try:
        commitment = await commitment_service.create_commitment(request)
    except CommitmentServiceError as error:
        raise _commitment_http_error(error) from error

    return CommitmentResponse(**commitment)


@router.patch("/{commitment_id}", response_model=CommitmentResponse)
async def update_commitment(
    commitment_id: str,
    request: CommitmentUpdateRequest,
    commitment_service: CommitmentService = Depends(get_commitment_service),
) -> CommitmentResponse:
    try:
        commitment = await commitment_service.update_commitment(commitment_id, request)
    except CommitmentServiceError as error:
        raise _commitment_http_error(error) from error

    return CommitmentResponse(**commitment)


@router.delete("/{commitment_id}", status_code=204)
async def deactivate_commitment(
    commitment_id: str,
    commitment_service: CommitmentService = Depends(get_commitment_service),
) -> Response:
    try:
        await commitment_service.deactivate_commitment(commitment_id)
    except CommitmentServiceError as error:
        raise _commitment_http_error(error) from error

    return Response(status_code=204)


def _commitment_http_error(error: CommitmentServiceError):
    from fastapi import HTTPException

    return HTTPException(status_code=error.status_code, detail=error.detail)
