from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.dependencies import get_entity_service
from app.models.entity import (
    EntityCreateRequest,
    EntityEventCreateRequest,
    EntityEventResponse,
    EntityEventType,
    EntityEventUpdateRequest,
    EntityResponse,
    EntityType,
    EntityUpdateRequest,
)
from app.services.entity_service import EntityService, EntityServiceError


router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityResponse])
async def list_entities(
    entity_type: Optional[EntityType] = Query(default=None),
    normalized_name: Optional[str] = Query(default=None),
    active: Optional[bool] = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    entity_service: EntityService = Depends(get_entity_service),
) -> list[EntityResponse]:
    try:
        entities = await entity_service.list_entities(
            entity_type=entity_type,
            normalized_name=normalized_name,
            active=active,
            limit=limit,
        )
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return [EntityResponse(**entity) for entity in entities]


@router.post("", response_model=EntityResponse, status_code=201)
async def create_entity(
    request: EntityCreateRequest,
    entity_service: EntityService = Depends(get_entity_service),
) -> EntityResponse:
    try:
        entity = await entity_service.create_entity(request)
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return EntityResponse(**entity)


@router.patch("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    request: EntityUpdateRequest,
    entity_service: EntityService = Depends(get_entity_service),
) -> EntityResponse:
    try:
        entity = await entity_service.update_entity(entity_id, request)
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return EntityResponse(**entity)


@router.delete("/{entity_id}", status_code=204)
async def deactivate_entity(
    entity_id: str,
    entity_service: EntityService = Depends(get_entity_service),
) -> Response:
    try:
        await entity_service.deactivate_entity(entity_id)
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return Response(status_code=204)


@router.get("/{entity_id}/events", response_model=list[EntityEventResponse])
async def list_entity_events(
    entity_id: str,
    event_type: Optional[EntityEventType] = Query(default=None),
    active: Optional[bool] = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    entity_service: EntityService = Depends(get_entity_service),
) -> list[EntityEventResponse]:
    try:
        events = await entity_service.list_entity_events(
            entity_id=entity_id,
            event_type=event_type,
            active=active,
            limit=limit,
        )
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return [EntityEventResponse(**event) for event in events]


@router.post("/{entity_id}/events", response_model=EntityEventResponse, status_code=201)
async def create_entity_event(
    entity_id: str,
    request: EntityEventCreateRequest,
    entity_service: EntityService = Depends(get_entity_service),
) -> EntityEventResponse:
    if request.entity_id != entity_id:
        raise HTTPException(status_code=400, detail="Entity ID mismatch.")

    try:
        event = await entity_service.create_entity_event(request)
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return EntityEventResponse(**event)


@router.patch("/events/{event_id}", response_model=EntityEventResponse)
async def update_entity_event(
    event_id: str,
    request: EntityEventUpdateRequest,
    entity_service: EntityService = Depends(get_entity_service),
) -> EntityEventResponse:
    try:
        event = await entity_service.update_entity_event(event_id, request)
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return EntityEventResponse(**event)


@router.delete("/events/{event_id}", status_code=204)
async def deactivate_entity_event(
    event_id: str,
    entity_service: EntityService = Depends(get_entity_service),
) -> Response:
    try:
        await entity_service.deactivate_entity_event(event_id)
    except EntityServiceError as error:
        raise _entity_http_error(error) from error

    return Response(status_code=204)


def _entity_http_error(error: EntityServiceError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)
