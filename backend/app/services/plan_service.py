from __future__ import annotations

import re
from typing import Any

from app.models.plan import (
    PlanCreateRequest,
    PlanMilestoneCreateRequest,
    PlanMilestoneUpdateRequest,
    PlanUpdateRequest,
)
from app.services.entity_normalization_service import EntityNormalizationService
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


class PlanServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class PlanService:
    def __init__(self, memory_service: SupabaseMemoryService) -> None:
        self.memory_service = memory_service
        self.normalization_service = EntityNormalizationService()

    async def create_plan(self, request: PlanCreateRequest) -> dict[str, Any]:
        payload = _payload(request)
        payload["title"] = _clean_required(payload.get("title"), "title")
        if "description" in payload:
            payload["description"] = _clean_optional(payload["description"])
        if "desired_outcome" in payload:
            payload["desired_outcome"] = _clean_optional(payload["desired_outcome"])
        payload = await self._normalize_entity_references(
            payload,
            text_fields=("title", "description", "desired_outcome"),
            link_field="primary_entity_id",
        )
        wrong_names = _correction_wrong_names(payload)

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
                wrong_names.update(_correction_wrong_names(duplicate))
                plan = await self._merge_existing_plan(duplicate, payload)
            else:
                corrected_duplicate = next(
                    (
                        plan
                        for plan in existing
                        if _plan_matches_corrected_duplicate(
                            plan,
                            payload,
                            wrong_names,
                        )
                    ),
                    None,
                )
                if corrected_duplicate:
                    wrong_names.update(_correction_wrong_names(corrected_duplicate))
                    plan = await self._merge_existing_plan(
                        corrected_duplicate,
                        _corrected_plan_payload(payload, wrong_names),
                    )
                else:
                    related_duplicate = _best_related_plan(existing, payload)
                    if related_duplicate:
                        plan = await self._merge_existing_plan(
                            related_duplicate,
                            _related_plan_payload(payload, related_duplicate),
                        )
                    else:
                        plan = await self.memory_service.create_plan(payload)
            wrong_names.update(_correction_wrong_names(plan))
            if wrong_names:
                await self._archive_superseded_plans(plan, wrong_names)
            return plan
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
        payload = await self._normalize_entity_references(
            payload,
            text_fields=("title", "description", "desired_outcome"),
            link_field="primary_entity_id",
        )

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
        payload = await self._normalize_entity_references(
            payload,
            text_fields=("title", "description"),
        )

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
        payload = await self._normalize_entity_references(
            payload,
            text_fields=("title", "description"),
        )

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
            "title",
            "description",
            "desired_outcome",
            "primary_entity_id",
            "source_conversation_id",
            "source_message_id",
            "source_memory_id",
            "start_date",
            "target_date",
        ):
            if payload.get(field) and payload.get(field) != existing.get(field):
                updates[field] = payload[field]
        if payload.get("status") and payload.get("status") != existing.get("status"):
            updates["status"] = payload["status"]
        if (
            payload.get("active") is not None
            and payload.get("active") != existing.get("active")
        ):
            updates["active"] = payload["active"]
        if payload.get("priority", 3) > existing.get("priority", 3):
            updates["priority"] = payload["priority"]
        metadata = {
            **(existing.get("metadata") or {}),
            **(payload.get("metadata") or {}),
        }
        if metadata != (existing.get("metadata") or {}):
            updates["metadata"] = metadata

        if not updates:
            return existing
        updated = await self.memory_service.update_plan(existing["id"], **updates)
        return updated or existing

    async def _archive_superseded_plans(
        self,
        corrected_plan: dict[str, Any],
        wrong_names: set[str],
    ) -> None:
        corrected_id = corrected_plan.get("id")
        if not corrected_id:
            return
        try:
            plans = await self.memory_service.list_plans(
                plan_type=corrected_plan.get("plan_type"),
                active=True,
                limit=100,
            )
        except MemoryServiceError:
            return

        for plan in plans:
            if plan.get("id") == corrected_id:
                continue
            if not _plan_contains_wrong_name(plan, wrong_names):
                continue
            metadata = {
                **(plan.get("metadata") or {}),
                "superseded_by_plan_id": corrected_id,
                "superseded_by_title": corrected_plan.get("title"),
                "cleanup_reason": "explicit_person_correction",
            }
            try:
                await self.memory_service.update_plan(
                    plan["id"],
                    active=False,
                    status="archived",
                    metadata=metadata,
                )
            except MemoryServiceError:
                continue

    async def _normalize_entity_references(
        self,
        payload: dict[str, Any],
        *,
        text_fields: tuple[str, ...],
        link_field: str | None = None,
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
            text_fields=text_fields,
            link_field=link_field,
        )
        return result.payload


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
    cleaned = _clean_optional(value)
    if not cleaned:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", " ", cleaned.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def _correction_wrong_names(payload: dict[str, Any]) -> set[str]:
    metadata = payload.get("metadata") or {}
    values: list[Any] = []
    for key in ("wrong_names", "wrong_name", "old_names", "old_name"):
        raw_value = metadata.get(key)
        if isinstance(raw_value, list):
            values.extend(raw_value)
        elif raw_value:
            values.append(raw_value)

    person_correction = metadata.get("person_correction")
    if isinstance(person_correction, dict):
        raw_value = person_correction.get("wrong_names")
        if isinstance(raw_value, list):
            values.extend(raw_value)
        elif raw_value:
            values.append(raw_value)

    for field in ("source_content",):
        values.extend(_wrong_names_from_text(metadata.get(field)))
    for field in ("title", "description", "desired_outcome"):
        values.extend(_wrong_names_from_text(payload.get(field)))

    return {_normalize_text(value) for value in values if _looks_like_wrong_name(value)}


def _wrong_names_from_text(value: Any) -> list[str]:
    text = _clean_optional(value)
    if not text:
        return []

    values: list[str] = []
    for pattern in (
        r"\b(?:corrected|replacing)\s+from\s+([A-Za-z0-9 ,/]+?)(?:[.!?)]|$)",
        r"\bpreviously\s+(?:referenced\s+as|called|known\s+as)\s+([A-Za-z0-9 ,/]+?)(?:[.!?)]|$)",
    ):
        for match in re.finditer(pattern, text, flags=re.I):
            values.extend(_split_wrong_name_text(match.group(1)))

    correction_context = re.search(
        r"\b(?:name|person|correction|corrected|wrong|mistaken|referenced)\b",
        text,
        flags=re.I,
    )
    if correction_context:
        values.extend(
            match.group(1)
            for match in re.finditer(r"\bnot\s+([A-Za-z0-9]{1,32})\b", text, re.I)
        )
    return values


def _split_wrong_name_text(value: str) -> list[str]:
    return [
        token
        for token in re.split(r"\s*(?:,|/|\bor\b|\band\b)\s*", value)
        if token
    ]


def _looks_like_wrong_name(value: Any) -> bool:
    cleaned = _clean_optional(value)
    if not cleaned:
        return False
    normalized = re.sub(r"[^a-z0-9]+", "", cleaned.casefold())
    if not normalized:
        return False
    return normalized not in {
        "a",
        "an",
        "as",
        "from",
        "name",
        "not",
        "or",
        "person",
        "previously",
        "referenced",
        "the",
    }


def _plan_text(plan: dict[str, Any]) -> str:
    return _normalize_text(
        " ".join(
            str(plan.get(field) or "")
            for field in ("title", "description", "desired_outcome")
        )
    )


PLAN_STOP_WORDS = {
    "about",
    "active",
    "after",
    "again",
    "and",
    "around",
    "for",
    "from",
    "have",
    "into",
    "next",
    "out",
    "plan",
    "planned",
    "planning",
    "successful",
    "take",
    "that",
    "the",
    "this",
    "with",
    "year",
}


def _plan_tokens(plan: dict[str, Any]) -> set[str]:
    return {
        token
        for token in _plan_text(plan).split()
        if len(token) > 2 and token not in PLAN_STOP_WORDS
    }


def _best_related_plan(
    existing: list[dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    scored = [
        (_plan_related_score(plan, payload), plan)
        for plan in existing
        if plan.get("active") is not False
        and plan.get("status", "active") == "active"
    ]
    scored = [(score, plan) for score, plan in scored if score > 0]
    if not scored:
        return None
    scored.sort(
        key=lambda item: (
            item[0],
            int(item[1].get("priority") or 3),
            str(item[1].get("updated_at") or item[1].get("created_at") or ""),
        ),
        reverse=True,
    )
    return scored[0][1]


def _plan_related_score(existing: dict[str, Any], payload: dict[str, Any]) -> int:
    existing_entity_id = existing.get("primary_entity_id")
    payload_entity_id = payload.get("primary_entity_id")
    if payload_entity_id and existing_entity_id == payload_entity_id:
        if payload.get("plan_type") == "dating":
            return 100
        return 85

    existing_tokens = _plan_tokens(existing)
    payload_tokens = _plan_tokens(payload)
    if not existing_tokens or not payload_tokens:
        return 0

    shared = existing_tokens & payload_tokens
    smaller_size = min(len(existing_tokens), len(payload_tokens))
    shared_ratio = len(shared) / smaller_size if smaller_size else 0

    if (
        payload.get("plan_type") == "dating"
        and existing.get("plan_type") == "dating"
        and _has_dating_plan_terms(existing_tokens)
        and _has_dating_plan_terms(payload_tokens)
        and shared
    ):
        return 75 + min(len(shared), 5)

    if len(shared) >= 4 and shared_ratio >= 0.55:
        return 65 + min(len(shared), 10)

    if len(shared) >= 3 and shared_ratio >= 0.7:
        return 60 + min(len(shared), 10)

    return 0


def _has_dating_plan_terms(tokens: set[str]) -> bool:
    return bool(tokens & {"date", "dating", "dinner", "restaurant", "monday", "week"})


def _related_plan_payload(
    payload: dict[str, Any],
    existing: dict[str, Any],
) -> dict[str, Any]:
    metadata = {
        **(payload.get("metadata") or {}),
        "merged_into_existing_plan_id": existing.get("id"),
        "merge_reason": "related_active_plan",
    }
    return {**payload, "metadata": metadata}


def _plan_contains_wrong_name(plan: dict[str, Any], wrong_names: set[str]) -> bool:
    if not wrong_names:
        return False
    return bool(set(_plan_text(plan).split()) & wrong_names)


def _plan_matches_corrected_duplicate(
    existing: dict[str, Any],
    payload: dict[str, Any],
    wrong_names: set[str],
) -> bool:
    if not wrong_names or not _plan_contains_wrong_name(existing, wrong_names):
        return False
    existing_entity_id = existing.get("primary_entity_id")
    payload_entity_id = payload.get("primary_entity_id")
    if payload_entity_id and existing_entity_id not in {None, payload_entity_id}:
        return False
    return bool(set(_plan_text(existing).split()) & set(_plan_text(payload).split()))


def _corrected_plan_payload(
    payload: dict[str, Any],
    wrong_names: set[str],
) -> dict[str, Any]:
    updated = dict(payload)
    corrected_display = _corrected_display_from_plan(payload, wrong_names)
    if not corrected_display:
        return updated

    for field in ("title", "description", "desired_outcome"):
        value = updated.get(field)
        if not value:
            continue
        for wrong_name in wrong_names:
            value = re.sub(
                rf"\b{re.escape(wrong_name)}\b",
                corrected_display,
                str(value),
                flags=re.I,
            )
        updated[field] = value
    return updated


def _corrected_display_from_plan(
    payload: dict[str, Any],
    wrong_names: set[str],
) -> str | None:
    text = str(payload.get("title") or "")
    for token in re.findall(r"\b[A-Z][a-z0-9]{1,24}\b", text):
        if _normalize_text(token) not in wrong_names:
            return token
    return None
