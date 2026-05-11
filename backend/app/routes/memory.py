from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.dependencies import get_memory_service
from app.models.memory import MemoryResponse, MemoryType, MemoryUpdateRequest
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=list[MemoryResponse])
async def list_memory(
    memory_type: Optional[MemoryType] = Query(default=None),
    active: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> list[MemoryResponse]:
    try:
        memories = await memory_service.list_long_term_memory(
            limit=limit,
            memory_type=memory_type,
            active=active,
        )
    except MemoryServiceError as error:
        raise _memory_http_error(error) from error

    return [MemoryResponse(**memory) for memory in memories]


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="At least one memory field must be provided.",
        )

    try:
        memory = await memory_service.update_long_term_memory(
            memory_id,
            **updates,
        )
    except MemoryServiceError as error:
        raise _memory_http_error(error) from error

    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found.")

    return MemoryResponse(**memory)


@router.delete("/{memory_id}", status_code=204)
async def deactivate_memory(
    memory_id: str,
    memory_service: SupabaseMemoryService = Depends(get_memory_service),
) -> Response:
    try:
        deactivated = await memory_service.deactivate_long_term_memory(memory_id)
    except MemoryServiceError as error:
        raise _memory_http_error(error) from error

    if not deactivated:
        raise HTTPException(status_code=404, detail="Memory not found.")

    return Response(status_code=204)


def _memory_http_error(error: MemoryServiceError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)
