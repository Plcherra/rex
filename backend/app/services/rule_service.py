from __future__ import annotations

import re
from typing import Any

from app.models.personal_rule import (
    PersonalRuleCreateRequest,
    PersonalRuleUpdateRequest,
)
from app.services.entity_normalization_service import EntityNormalizationService
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


class RuleServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class RuleService:
    def __init__(self, memory_service: SupabaseMemoryService) -> None:
        self.memory_service = memory_service
        self.normalization_service = EntityNormalizationService()

    async def create_rule(self, request: PersonalRuleCreateRequest) -> dict[str, Any]:
        payload = _payload(request)
        payload["title"] = _clean_required(payload.get("title"), "title")
        payload["rule_text"] = _clean_required(payload.get("rule_text"), "rule_text")
        payload["trigger_keywords"] = _dedupe_strings(
            payload.get("trigger_keywords", [])
        )
        payload = await self._normalize_entity_references(payload)

        try:
            existing = await self.memory_service.list_personal_rules(
                rule_type=payload["rule_type"],
                active=True,
                limit=100,
            )
            duplicate = next(
                (
                    rule
                    for rule in existing
                    if _normalize_text(rule.get("rule_text"))
                    == _normalize_text(payload["rule_text"])
                ),
                None,
            )
            if duplicate:
                return await self._merge_existing_rule(duplicate, payload)
            return await self.memory_service.create_personal_rule(payload)
        except MemoryServiceError as error:
            raise RuleServiceError(error.detail, error.status_code) from error

    async def list_rules(
        self,
        *,
        rule_type: str | None = None,
        status: str | None = None,
        active: bool | None = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self.memory_service.list_personal_rules(
                rule_type=rule_type,
                status=status,
                active=active,
                limit=limit,
            )
        except MemoryServiceError as error:
            raise RuleServiceError(error.detail, error.status_code) from error

    async def update_rule(
        self, rule_id: str, request: PersonalRuleUpdateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        if "title" in payload:
            payload["title"] = _clean_required(payload["title"], "title")
        if "rule_text" in payload:
            payload["rule_text"] = _clean_required(payload["rule_text"], "rule_text")
        if "trigger_keywords" in payload:
            payload["trigger_keywords"] = _dedupe_strings(payload["trigger_keywords"])
        payload = await self._normalize_entity_references(payload)

        try:
            updated = await self.memory_service.update_personal_rule(rule_id, **payload)
        except MemoryServiceError as error:
            raise RuleServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise RuleServiceError("Personal rule not found.", 404)
        return updated

    async def deactivate_rule(self, rule_id: str) -> dict[str, Any]:
        try:
            updated = await self.memory_service.deactivate_personal_rule(rule_id)
        except MemoryServiceError as error:
            raise RuleServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise RuleServiceError("Personal rule not found.", 404)
        return updated

    async def _merge_existing_rule(
        self, existing: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        keywords = _dedupe_strings(
            [*existing.get("trigger_keywords", []), *payload.get("trigger_keywords", [])]
        )
        if keywords != existing.get("trigger_keywords", []):
            updates["trigger_keywords"] = keywords
        if payload.get("priority", 3) > existing.get("priority", 3):
            updates["priority"] = payload["priority"]
        for field in ("source_conversation_id", "source_message_id", "source_memory_id"):
            if payload.get(field) and not existing.get(field):
                updates[field] = payload[field]
        metadata = {**(existing.get("metadata") or {}), **(payload.get("metadata") or {})}
        if metadata != (existing.get("metadata") or {}):
            updates["metadata"] = metadata

        if not updates:
            return existing
        updated = await self.memory_service.update_personal_rule(
            existing["id"], **updates
        )
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
            text_fields=("title", "rule_text", "trigger_keywords"),
        )
        return result.payload


def is_active_rule(rule: dict[str, Any]) -> bool:
    return rule.get("active") is not False and rule.get("status", "active") == "active"


def _payload(request: Any) -> dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump(exclude_none=True)
    return {key: value for key, value in dict(request).items() if value is not None}


def _clean_required(value: Any, field_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if not cleaned:
        raise RuleServiceError(f"{field_name} is required.", 422)
    return cleaned


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _dedupe_strings(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        cleaned = re.sub(r"\s+", " ", str(value)).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result
