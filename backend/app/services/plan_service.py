from __future__ import annotations

import re
from typing import Any

from app.models.plan import (
    PlanCreateRequest,
    PlanMilestoneCreateRequest,
    PlanMilestoneUpdateRequest,
    PlanUpdateRequest,
)
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


class PlanServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class PlanService:
    def __init__(self, memory_service: SupabaseMemoryService) -> None:
        self.memory_service = memory_service

    async def create_plan(self, request: PlanCreateRequest) -> dict[str, Any]:
        payload = _payload(request)
        payload["title"] = _clean_required(payload.get("title"), "title")
        if "description" in payload:
            payload["description"] = _clean_optional(payload["description"])
        if "desired_outcome" in payload:
            payload["desired_outcome"] = _clean_optional(payload["desired_outcome"])

        try:
            existing = await self.memory_service.list_plans(
                plan_type=payload["plan_type"],
                active=True,
                limit=100,
            )
            duplicate = next(
                (
                    plan
                    for plan in existing
                    if _normalize_text(plan.get("title"))
                    == _normalize_text(payload["title"])
                ),
                None,
            )
            if duplicate:
                return await self._merge_existing_plan(duplicate, payload)
            return await self.memory_service.create_plan(payload)
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error

    async def list_plans(
        self,
        *,
        plan_type: str | None = None,
        status: str | None = None,
        active: bool | None = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self.memory_service.list_plans(
                plan_type=plan_type,
                status=status,
                active=active,
                limit=limit,
            )
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error

    async def update_plan(
        self, plan_id: str, request: PlanUpdateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        if "title" in payload:
            payload["title"] = _clean_required(payload["title"], "title")
        if "description" in payload:
            payload["description"] = _clean_optional(payload["description"])
        if "desired_outcome" in payload:
            payload["desired_outcome"] = _clean_optional(payload["desired_outcome"])

        try:
            updated = await self.memory_service.update_plan(plan_id, **payload)
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise PlanServiceError("Plan not found.", 404)
        return updated

    async def deactivate_plan(self, plan_id: str) -> dict[str, Any]:
        try:
            updated = await self.memory_service.deactivate_plan(plan_id)
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise PlanServiceError("Plan not found.", 404)
        return updated

    async def create_milestone(
        self, request: PlanMilestoneCreateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        payload["title"] = _clean_required(payload.get("title"), "title")
        if "description" in payload:
            payload["description"] = _clean_optional(payload["description"])

        try:
            return await self.memory_service.create_plan_milestone(payload)
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error

    async def list_milestones(
        self,
        *,
        plan_id: str | None = None,
        status: str | None = None,
        active: bool | None = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self.memory_service.list_plan_milestones(
                plan_id=plan_id,
                status=status,
                active=active,
                limit=limit,
            )
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error

    async def update_milestone(
        self, milestone_id: str, request: PlanMilestoneUpdateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        if "title" in payload:
            payload["title"] = _clean_required(payload["title"], "title")
        if "description" in payload:
            payload["description"] = _clean_optional(payload["description"])

        try:
            updated = await self.memory_service.update_plan_milestone(
                milestone_id, **payload
            )
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise PlanServiceError("Plan milestone not found.", 404)
        return updated

    async def deactivate_milestone(self, milestone_id: str) -> dict[str, Any]:
        try:
            updated = await self.memory_service.deactivate_plan_milestone(milestone_id)
        except MemoryServiceError as error:
            raise PlanServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise PlanServiceError("Plan milestone not found.", 404)
        return updated

    async def _merge_existing_plan(
        self, existing: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for field in (
            "description",
            "desired_outcome",
            "primary_entity_id",
            "source_conversation_id",
            "source_message_id",
            "source_memory_id",
            "start_date",
            "target_date",
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
        updated = await self.memory_service.update_plan(existing["id"], **updates)
        return updated or existing


def _payload(request: Any) -> dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump(exclude_none=True)
    return {key: value for key, value in dict(request).items() if value is not None}


def is_active_plan(plan: dict[str, Any]) -> bool:
    return (
        plan.get("active") is not False
        and plan.get("status", "active") == "active"
    )


def is_open_milestone(milestone: dict[str, Any]) -> bool:
    return (
        milestone.get("active") is not False
        and milestone.get("status", "open") in {"open", "in_progress"}
    )


def _clean_required(value: Any, field_name: str) -> str:
    cleaned = _clean_optional(value)
    if not cleaned:
        raise PlanServiceError(f"{field_name} is required.", 422)
    return cleaned


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()
