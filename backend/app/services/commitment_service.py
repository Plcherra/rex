from __future__ import annotations

import re
from typing import Any

from app.models.commitment import CommitmentCreateRequest, CommitmentUpdateRequest
from app.services.entity_normalization_service import EntityNormalizationService
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


class CommitmentServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class CommitmentService:
    def __init__(self, memory_service: SupabaseMemoryService) -> None:
        self.memory_service = memory_service
        self.normalization_service = EntityNormalizationService()

    async def create_commitment(
        self, request: CommitmentCreateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        payload["title"] = _clean_required(payload.get("title"), "title")
        payload["commitment_text"] = _clean_required(
            payload.get("commitment_text"), "commitment_text"
        )
        payload = await self._normalize_entity_references(payload)

        try:
            existing = await self.memory_service.list_commitments(
                commitment_type=payload["commitment_type"],
                active=True,
                limit=100,
            )
            duplicate = next(
                (
                    commitment
                    for commitment in existing
                    if self._matches_existing_commitment(commitment, payload)
                ),
                None,
            )
            if duplicate:
                return await self._merge_existing_commitment(duplicate, payload)
            return await self.memory_service.create_commitment(payload)
        except MemoryServiceError as error:
            raise CommitmentServiceError(error.detail, error.status_code) from error

    async def list_commitments(
        self,
        *,
        commitment_type: str | None = None,
        milestone_id: str | None = None,
        status: str | None = None,
        active: bool | None = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self.memory_service.list_commitments(
                commitment_type=commitment_type,
                milestone_id=milestone_id,
                status=status,
                active=active,
                limit=limit,
            )
        except MemoryServiceError as error:
            raise CommitmentServiceError(error.detail, error.status_code) from error

    async def update_commitment(
        self, commitment_id: str, request: CommitmentUpdateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        if "title" in payload:
            payload["title"] = _clean_required(payload["title"], "title")
        if "commitment_text" in payload:
            payload["commitment_text"] = _clean_required(
                payload["commitment_text"], "commitment_text"
            )
        payload = await self._normalize_entity_references(payload)

        try:
            updated = await self.memory_service.update_commitment(
                commitment_id, **payload
            )
        except MemoryServiceError as error:
            raise CommitmentServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise CommitmentServiceError("Commitment not found.", 404)
        return updated

    async def deactivate_commitment(self, commitment_id: str) -> dict[str, Any]:
        try:
            updated = await self.memory_service.deactivate_commitment(commitment_id)
        except MemoryServiceError as error:
            raise CommitmentServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise CommitmentServiceError("Commitment not found.", 404)
        return updated

    def _matches_existing_commitment(
        self, existing: dict[str, Any], payload: dict[str, Any]
    ) -> bool:
        if existing.get("status") not in {"open", "in_progress"}:
            return False
        if _normalize_text(existing.get("commitment_text")) != _normalize_text(
            payload["commitment_text"]
        ):
            return False
        return (
            existing.get("plan_id") == payload.get("plan_id")
            and existing.get("milestone_id") == payload.get("milestone_id")
            and existing.get("entity_id") == payload.get("entity_id")
        )

    async def _merge_existing_commitment(
        self, existing: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for field in (
            "source_conversation_id",
            "source_message_id",
            "source_memory_id",
            "due_at",
            "milestone_id",
        ):
            if payload.get(field) and not existing.get(field):
                updates[field] = payload[field]
        if payload.get("priority", 3) > existing.get("priority", 3):
            updates["priority"] = payload["priority"]
        metadata = {**(existing.get("metadata") or {}), **(payload.get("metadata") or {})}
        if metadata != (existing.get("metadata") or {}):
            updates["metadata"] = metadata

        if not updates:
            return existing
        updated = await self.memory_service.update_commitment(existing["id"], **updates)
        return updated or existing

    async def _normalize_entity_references(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        list_entities = getattr(self.memory_service, "list_entities", None)
        if list_entities is None:
            return payload
        try:
            entities = await list_entities(active=True, limit=100)
        except Exception:
            return payload
        result = self.normalization_service.normalize_payload_references(
            payload,
            entities,
            text_fields=("title", "commitment_text"),
            link_field="entity_id",
        )
        return result.payload


def is_open_commitment(commitment: dict[str, Any]) -> bool:
    return (
        commitment.get("active") is not False
        and commitment.get("status", "open") in {"open", "in_progress"}
    )


def _payload(request: Any) -> dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump(exclude_none=True)
    return {key: value for key, value in dict(request).items() if value is not None}


def _clean_required(value: Any, field_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if not cleaned:
        raise CommitmentServiceError(f"{field_name} is required.", 422)
    return cleaned


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()
