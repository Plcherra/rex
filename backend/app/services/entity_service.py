from __future__ import annotations

import re
from typing import Any

from app.models.entity import (
    EntityCreateRequest,
    EntityEventCreateRequest,
    EntityEventUpdateRequest,
    EntityUpdateRequest,
)
from app.services.entity_normalization_service import EntityNormalizationService
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
        self.normalization_service = EntityNormalizationService()

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
        normalized_source = (
            display_name
            if payload.get("entity_type") == "person"
            else original_normalized_name or display_name
        )
        payload["normalized_name"] = _normalize_entity_name(normalized_source)
        payload["aliases"] = _entity_aliases(
            payload,
            original_display_name=original_display_name,
            original_normalized_name=original_normalized_name,
            original_aliases=original_aliases,
            display_name=display_name,
        )
        wrong_names = _correction_wrong_names(payload)

        try:
            existing = await self.memory_service.list_entities(
                entity_type=payload["entity_type"],
                active=True,
                limit=100,
            )
            normalized = self.normalization_service.normalize_candidate_entity(
                payload,
                existing,
            )
            payload = normalized.payload
            wrong_names.update(normalized.obsolete_names)
            duplicate = next(
                (
                    entity
                    for entity in existing
                    if _entity_matches_payload(
                        entity,
                        payload,
                        ignore_alias_matches=bool(wrong_names),
                    )
                ),
                None,
            )
            if duplicate is None and normalized.canonical_entity is not None:
                duplicate = normalized.canonical_entity
            if duplicate:
                wrong_names.update(_correction_wrong_names(duplicate))
                entity = await self._merge_existing_entity(duplicate, payload)
            else:
                entity = await self.memory_service.create_entity(payload)
            wrong_names.update(_correction_wrong_names(entity))
            if wrong_names:
                entity = await self._remove_wrong_aliases(entity, wrong_names)
                await self._archive_superseded_entities(entity, wrong_names)
            return entity
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

    async def _archive_superseded_entities(
        self,
        corrected_entity: dict[str, Any],
        wrong_names: set[str],
    ) -> None:
        corrected_id = corrected_entity.get("id")
        if not corrected_id:
            return

        try:
            entities = await self.memory_service.list_entities(
                entity_type=corrected_entity.get("entity_type"),
                active=True,
                limit=100,
            )
        except MemoryServiceError:
            return

        for entity in entities:
            if entity.get("id") == corrected_id:
                continue
            if not _is_superseded_entity(entity, wrong_names):
                continue

            metadata = {
                **(entity.get("metadata") or {}),
                "superseded_by_entity_id": corrected_id,
                "superseded_by_display_name": corrected_entity.get("display_name"),
                "cleanup_reason": "explicit_person_correction",
            }
            try:
                await self.memory_service.update_entity(
                    entity["id"],
                    active=False,
                    status="inactive",
                    metadata=metadata,
                )
            except MemoryServiceError:
                continue

    async def _remove_wrong_aliases(
        self,
        entity: dict[str, Any],
        wrong_names: set[str],
    ) -> dict[str, Any]:
        aliases = entity.get("aliases", [])
        cleaned_aliases = [
            alias
            for alias in aliases
            if _safe_normalize_entity_name(alias) not in wrong_names
        ]
        if cleaned_aliases == aliases:
            return entity

        metadata = {
            **(entity.get("metadata") or {}),
            "removed_wrong_aliases": [
                alias
                for alias in aliases
                if _safe_normalize_entity_name(alias) in wrong_names
            ],
            "cleanup_reason": "explicit_person_correction",
        }
        try:
            updated = await self.memory_service.update_entity(
                entity["id"],
                aliases=cleaned_aliases,
                metadata=metadata,
            )
        except MemoryServiceError:
            return entity
        return updated or {**entity, "aliases": cleaned_aliases, "metadata": metadata}


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


def _entity_match_keys(
    entity: dict[str, Any],
    *,
    include_aliases: bool = True,
) -> set[str]:
    raw_values = [
        entity.get("normalized_name"),
        entity.get("display_name"),
    ]
    if include_aliases:
        raw_values.extend(entity.get("aliases", []))
    return {
        _normalize_entity_name(value)
        for value in raw_values
        if _clean_optional(value)
    }


def _entity_matches_payload(
    entity: dict[str, Any],
    payload: dict[str, Any],
    *,
    ignore_alias_matches: bool = False,
) -> bool:
    existing_keys = _entity_match_keys(
        entity,
        include_aliases=not ignore_alias_matches,
    )
    incoming_keys = _entity_match_keys(
        payload,
        include_aliases=not ignore_alias_matches,
    )
    return bool(existing_keys & incoming_keys)


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
    for field in ("relationship", "summary"):
        values.extend(_wrong_names_from_text(payload.get(field)))

    return {
        _normalize_entity_name(value)
        for value in values
        if _looks_like_wrong_name(value)
    }


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


def _is_superseded_entity(entity: dict[str, Any], wrong_names: set[str]) -> bool:
    keys = _entity_match_keys(entity)
    if keys & wrong_names:
        return True

    normalized_name = _safe_normalize_entity_name(entity.get("normalized_name"))
    display_name = _safe_normalize_entity_name(entity.get("display_name"))
    if normalized_name in {"next week date", "date plan"} or display_name in {
        "next week date",
        "date plan",
    }:
        text = _safe_normalize_entity_name(
            " ".join(
                str(entity.get(field) or "")
                for field in ("relationship", "summary")
            )
        )
        return bool(set(text.split()) & wrong_names)

    return False


def _safe_normalize_entity_name(value: Any) -> str:
    if not _clean_optional(value):
        return ""
    try:
        return _normalize_entity_name(value)
    except EntityServiceError:
        return ""


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
