from __future__ import annotations

import re
from typing import Any

from app.models.entity import (
    EntityCreateRequest,
    EntityEventCreateRequest,
    EntityEventUpdateRequest,
    EntityUpdateRequest,
)
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService

ENTITY_DESCRIPTOR_PREFIXES = (
    "the girl ",
    "a girl ",
    "girl ",
    "the guy ",
    "a guy ",
    "guy ",
    "the person ",
    "a person ",
    "person ",
)

ENTITY_DESCRIPTOR_SUFFIXES = (
    " from work",
    " at work",
    " from school",
    " from church",
    " from gym",
    " from the gym",
)

PERSON_DESCRIPTOR_ALIASES = (
    ("girl from work", r"\b(?:the |a |that )?girl from work\b"),
    ("guy from work", r"\b(?:the |a |that )?guy from work\b"),
    ("person from work", r"\b(?:the |a |that )?person from work\b"),
    ("coworker", r"\bcoworker\b"),
)


class EntityServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class EntityService:
    def __init__(self, memory_service: SupabaseMemoryService) -> None:
        self.memory_service = memory_service

    async def create_entity(self, request: EntityCreateRequest) -> dict[str, Any]:
        payload = _payload(request)
        original_display_name = _clean_required(
            payload.get("display_name"), "display_name"
        )
        original_normalized_name = _clean_optional(payload.get("normalized_name"))
        original_aliases = _dedupe_strings(payload.get("aliases", []))
        display_name = _canonical_display_name(
            payload.get("entity_type"),
            original_display_name,
            original_normalized_name,
            original_aliases,
        )
        payload["display_name"] = display_name
        payload["normalized_name"] = _normalize_entity_name(
            display_name if payload.get("entity_type") == "person" else (
                original_normalized_name or display_name
            )
        )
        payload["aliases"] = _entity_aliases(
            payload,
            original_display_name=original_display_name,
            original_normalized_name=original_normalized_name,
            original_aliases=original_aliases,
            display_name=display_name,
        )

        try:
            existing = await self.memory_service.list_entities(
                entity_type=payload["entity_type"],
                active=True,
                limit=100,
            )
            duplicate = next(
                (
                    entity
                    for entity in existing
                    if _entity_matches_payload(entity, payload)
                ),
                None,
            )
            if duplicate:
                return await self._merge_existing_entity(duplicate, payload)
            return await self.memory_service.create_entity(payload)
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error

    async def list_entities(
        self,
        *,
        entity_type: str | None = None,
        normalized_name: str | None = None,
        active: bool | None = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self.memory_service.list_entities(
                entity_type=entity_type,
                normalized_name=(
                    _normalize_key(normalized_name) if normalized_name else None
                ),
                active=active,
                limit=limit,
            )
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error

    async def update_entity(
        self, entity_id: str, request: EntityUpdateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        if "display_name" in payload:
            payload["display_name"] = _clean_required(
                payload["display_name"], "display_name"
            )
        if "normalized_name" in payload:
            payload["normalized_name"] = _normalize_entity_name(
                payload["normalized_name"]
            )
        elif "display_name" in payload:
            payload["normalized_name"] = _normalize_entity_name(payload["display_name"])
        if "aliases" in payload:
            payload["aliases"] = _dedupe_strings(payload["aliases"])

        try:
            updated = await self.memory_service.update_entity(entity_id, **payload)
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise EntityServiceError("Entity not found.", 404)
        return updated

    async def deactivate_entity(self, entity_id: str) -> dict[str, Any]:
        try:
            updated = await self.memory_service.deactivate_entity(entity_id)
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise EntityServiceError("Entity not found.", 404)
        return updated

    async def create_entity_event(
        self, request: EntityEventCreateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        payload["content"] = _clean_required(payload.get("content"), "content")
        if payload.get("title") is not None:
            payload["title"] = _clean_optional(payload["title"])

        try:
            return await self.memory_service.create_entity_event(payload)
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error

    async def list_entity_events(
        self,
        *,
        entity_id: str | None = None,
        event_type: str | None = None,
        active: bool | None = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self.memory_service.list_entity_events(
                entity_id=entity_id,
                event_type=event_type,
                active=active,
                limit=limit,
            )
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error

    async def update_entity_event(
        self, event_id: str, request: EntityEventUpdateRequest
    ) -> dict[str, Any]:
        payload = _payload(request)
        if "content" in payload:
            payload["content"] = _clean_required(payload["content"], "content")
        if "title" in payload:
            payload["title"] = _clean_optional(payload["title"])

        try:
            updated = await self.memory_service.update_entity_event(event_id, **payload)
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise EntityServiceError("Entity event not found.", 404)
        return updated

    async def deactivate_entity_event(self, event_id: str) -> dict[str, Any]:
        try:
            updated = await self.memory_service.deactivate_entity_event(event_id)
        except MemoryServiceError as error:
            raise EntityServiceError(error.detail, error.status_code) from error
        if updated is None:
            raise EntityServiceError("Entity event not found.", 404)
        return updated

    async def _merge_existing_entity(
        self, existing: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        aliases = _dedupe_strings(
            [*existing.get("aliases", []), *payload.get("aliases", [])]
        )
        if aliases != existing.get("aliases", []):
            updates["aliases"] = aliases

        for field in (
            "relationship",
            "summary",
            "source_conversation_id",
            "source_message_id",
            "source_memory_id",
        ):
            if payload.get(field) and not existing.get(field):
                updates[field] = payload[field]

        if payload.get("importance", 3) > existing.get("importance", 3):
            updates["importance"] = payload["importance"]

        metadata = _merge_metadata(existing.get("metadata"), payload.get("metadata"))
        if metadata != (existing.get("metadata") or {}):
            updates["metadata"] = metadata

        if not updates:
            return existing

        updated = await self.memory_service.update_entity(existing["id"], **updates)
        return updated or existing


def _payload(request: Any) -> dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump(exclude_none=True)
    return {key: value for key, value in dict(request).items() if value is not None}


def _clean_required(value: Any, field_name: str) -> str:
    cleaned = _clean_optional(value)
    if not cleaned:
        raise EntityServiceError(f"{field_name} is required.", 422)
    return cleaned


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _normalize_key(value: Any) -> str:
    cleaned = _clean_required(value, "normalized_name").lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", cleaned)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        raise EntityServiceError("normalized_name is required.", 422)
    return normalized


def _normalize_entity_name(value: Any) -> str:
    normalized = _normalize_key(value)
    stripped = _strip_entity_descriptors(normalized)
    return stripped or normalized


def _strip_entity_descriptors(normalized: str) -> str | None:
    stripped = normalized
    for prefix in ENTITY_DESCRIPTOR_PREFIXES:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :].strip()
            break
    for suffix in ENTITY_DESCRIPTOR_SUFFIXES:
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)].strip()
            break
    if not stripped or _is_descriptor_fragment(stripped):
        return None
    return stripped


def _canonical_display_name(
    entity_type: str | None,
    display_name: str,
    normalized_name: str | None,
    aliases: list[str],
) -> str:
    if entity_type != "person":
        return display_name
    for value in (display_name, normalized_name, *aliases):
        canonical = _canonical_person_name(value)
        if canonical:
            return canonical
    return display_name


def _canonical_person_name(value: Any) -> str | None:
    cleaned = _clean_optional(value)
    if not cleaned:
        return None
    canonical = re.sub(
        r"^(?:the |a |that )?(?:girl|guy|person|woman|man)\s+",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    canonical = re.sub(
        r"\s+(?:from|at)\s+(?:work|school|church|the gym|gym)$",
        "",
        canonical,
        flags=re.I,
    ).strip()
    if not canonical:
        return None
    normalized = _normalize_key(canonical)
    if _is_descriptor_fragment(normalized):
        return None
    return canonical


def _entity_aliases(
    payload: dict[str, Any],
    *,
    original_display_name: str,
    original_normalized_name: str | None,
    original_aliases: list[str],
    display_name: str,
) -> list[str]:
    aliases = [*original_aliases]
    if payload.get("entity_type") == "person":
        aliases.extend([original_display_name, original_normalized_name or ""])
        aliases.extend(
            _person_descriptor_aliases(
                " ".join(
                    str(payload.get(field) or "")
                    for field in ("relationship", "summary")
                )
            )
        )
    aliases = _dedupe_strings(aliases)
    return [alias for alias in aliases if alias.casefold() != display_name.casefold()]


def _person_descriptor_aliases(text: str) -> list[str]:
    aliases = []
    for alias, pattern in PERSON_DESCRIPTOR_ALIASES:
        if re.search(pattern, text, flags=re.I):
            aliases.append(alias)
    return aliases


def _is_descriptor_fragment(value: str) -> bool:
    return value in {
        "girl",
        "guy",
        "person",
        "woman",
        "man",
        "work",
        "from work",
        "at work",
        "school",
        "from school",
        "at school",
        "church",
        "from church",
        "gym",
        "from gym",
        "from the gym",
        "dating interest",
        "date",
        "coworker",
    }


def is_active_entity_event(event: dict[str, Any]) -> bool:
    return event.get("active") is not False


def entity_event_accountability_text(event: dict[str, Any]) -> str:
    return " ".join(
        str(event.get(field) or "")
        for field in ("title", "content", "event_type")
    )


def _entity_match_keys(entity: dict[str, Any]) -> set[str]:
    raw_values = [
        entity.get("normalized_name"),
        entity.get("display_name"),
        *entity.get("aliases", []),
    ]
    return {
        _normalize_entity_name(value)
        for value in raw_values
        if _clean_optional(value)
    }


def _entity_matches_payload(
    entity: dict[str, Any],
    payload: dict[str, Any],
) -> bool:
    existing_keys = _entity_match_keys(entity)
    incoming_keys = _entity_match_keys(payload)
    return bool(existing_keys & incoming_keys)


def _dedupe_strings(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        cleaned = _clean_optional(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _merge_metadata(
    existing: dict[str, Any] | None, incoming: dict[str, Any] | None
) -> dict[str, Any]:
    return {**(existing or {}), **(incoming or {})}
