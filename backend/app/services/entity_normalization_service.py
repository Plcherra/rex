from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


CANONICAL_METADATA_KEYS = (
    "canonical_entity_id",
    "canonical_display_name",
    "canonical_normalized_name",
    "alias_source",
    "obsolete_aliases",
    "obsolete_names",
    "removed_wrong_aliases",
    "correction_confidence",
)

OBSOLETE_METADATA_KEYS = (
    "obsolete_aliases",
    "obsolete_names",
    "wrong_names",
    "old_names",
    "removed_wrong_aliases",
)

TEXT_REFERENCE_FIELDS = {
    "title",
    "description",
    "desired_outcome",
    "rule_text",
    "commitment_text",
    "summary",
    "relationship",
    "content",
}


@dataclass
class EntityCorrection:
    old_value: str
    new_value: str
    entity_type: Optional[str] = None
    confidence: float = 0.9

    @property
    def old_key(self) -> str:
        return normalize_entity_key(self.old_value)

    @property
    def new_key(self) -> str:
        return normalize_entity_key(self.new_value)


@dataclass
class EntityNormalizationResult:
    payload: dict[str, Any]
    canonical_entity: Optional[dict[str, Any]] = None
    obsolete_names: set[str] = field(default_factory=set)
    changed: bool = False


class EntityNormalizationService:
    """Canonical entity-name handling shared by memory write paths."""

    def normalize_candidate_entity(
        self,
        candidate: dict[str, Any],
        known_entities: Iterable[dict[str, Any]],
    ) -> EntityNormalizationResult:
        payload = dict(candidate)
        metadata = dict(payload.get("metadata") or {})
        entity_type = _clean_text(payload.get("entity_type"))
        raw_name = _clean_text(
            payload.get("display_name") or payload.get("normalized_name")
        )
        aliases = _dedupe_strings(payload.get("aliases") or [])
        obsolete_names = _obsolete_names_from_payload(payload)

        canonical = None
        if raw_name:
            canonical = self.detect_obsolete_alias(
                raw_name,
                known_entities,
                entity_type=entity_type,
            )

        if canonical is None:
            cleaned_aliases = [
                alias
                for alias in aliases
                if normalize_entity_key(alias) not in obsolete_names
            ]
            payload["aliases"] = cleaned_aliases
            if obsolete_names:
                metadata.update(
                    {
                        "obsolete_aliases": sorted(obsolete_names),
                        "alias_source": "explicit_correction",
                        "correction_confidence": 0.9,
                    }
                )
                payload["metadata"] = metadata
            return EntityNormalizationResult(
                payload=payload,
                obsolete_names=obsolete_names,
                changed=cleaned_aliases != aliases or bool(obsolete_names),
            )

        canonical_display = str(canonical.get("display_name") or raw_name or "").strip()
        canonical_normalized = normalize_entity_key(
            canonical.get("normalized_name") or canonical_display
        )
        all_obsolete = obsolete_names | _obsolete_names_for_entity(canonical)
        if raw_name:
            raw_key = normalize_entity_key(raw_name)
            if raw_key and raw_key != canonical_normalized:
                all_obsolete.add(raw_key)

        payload["display_name"] = canonical_display
        payload["normalized_name"] = canonical_normalized
        if canonical.get("entity_type"):
            payload["entity_type"] = canonical["entity_type"]
        payload["aliases"] = [
            alias
            for alias in aliases
            if normalize_entity_key(alias)
            not in {canonical_normalized, *all_obsolete}
        ]
        metadata.update(
            {
                "canonical_entity_id": canonical.get("id"),
                "canonical_display_name": canonical_display,
                "canonical_normalized_name": canonical_normalized,
                "alias_source": "entity_normalization",
                "obsolete_aliases": sorted(all_obsolete),
                "correction_confidence": 0.9,
            }
        )
        payload["metadata"] = metadata
        return EntityNormalizationResult(
            payload=payload,
            canonical_entity=canonical,
            obsolete_names=all_obsolete,
            changed=True,
        )

    def resolve_canonical_name(
        self,
        raw_name: Any,
        entity_type: Optional[str] = None,
        known_entities: Optional[Iterable[dict[str, Any]]] = None,
    ) -> str:
        cleaned = _clean_text(raw_name)
        if not cleaned:
            return ""
        if known_entities is not None:
            entity = self.detect_obsolete_alias(
                cleaned,
                known_entities,
                entity_type=entity_type,
            ) or self._detect_alias_entity(
                [cleaned],
                known_entities,
                entity_type=entity_type,
            )
            if entity is not None:
                return str(entity.get("display_name") or cleaned)
        return cleaned

    def detect_obsolete_alias(
        self,
        raw_name: Any,
        known_entities: Iterable[dict[str, Any]],
        *,
        entity_type: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        raw_key = normalize_entity_key(raw_name)
        if not raw_key:
            return None
        for entity in known_entities:
            if entity_type and entity.get("entity_type") != entity_type:
                continue
            if raw_key in _obsolete_names_for_entity(entity):
                return entity
        return None

    def apply_user_correction(
        self,
        old_value: Any,
        new_value: Any,
        entity_type: Optional[str] = None,
    ) -> EntityCorrection:
        old_clean = _clean_text(old_value) or ""
        new_clean = _clean_text(new_value) or ""
        return EntityCorrection(
            old_value=old_clean,
            new_value=new_clean,
            entity_type=entity_type,
        )

    def normalize_payload_references(
        self,
        payload: dict[str, Any],
        known_entities: Iterable[dict[str, Any]],
        *,
        text_fields: Iterable[str],
        link_field: Optional[str] = None,
    ) -> EntityNormalizationResult:
        updated = dict(payload)
        metadata = dict(updated.get("metadata") or {})
        replacements: dict[str, str] = {}
        canonical_entity: Optional[dict[str, Any]] = None
        obsolete_names: set[str] = set()

        for entity in known_entities:
            display = _clean_text(entity.get("display_name"))
            if not display:
                continue
            for obsolete in _obsolete_names_for_entity(entity):
                if obsolete:
                    replacements[obsolete] = display
                    obsolete_names.add(obsolete)

        changed = False
        for field_name in text_fields:
            value = updated.get(field_name)
            if isinstance(value, list):
                rewritten = [
                    _replace_obsolete_name_refs(item, replacements)
                    for item in value
                ]
                if rewritten != value:
                    updated[field_name] = rewritten
                    changed = True
                continue
            if field_name not in updated:
                continue
            rewritten = _replace_obsolete_name_refs(value, replacements)
            if rewritten != value:
                updated[field_name] = rewritten
                changed = True

        text = normalize_entity_key(
            " ".join(
                str(updated.get(field_name) or "")
                for field_name in text_fields
                if not isinstance(updated.get(field_name), list)
            )
            + " "
            + " ".join(
                str(item)
                for field_name in text_fields
                if isinstance(updated.get(field_name), list)
                for item in updated.get(field_name) or []
            )
        )
        for entity in known_entities:
            entity_obsolete = _obsolete_names_for_entity(entity)
            entity_keys = _entity_keys(entity, include_aliases=True)
            if text and (entity_obsolete & set(text.split()) or entity_keys & set(text.split())):
                canonical_entity = entity
                break

        if link_field and not updated.get(link_field) and canonical_entity:
            if canonical_entity.get("id"):
                updated[link_field] = canonical_entity["id"]
                changed = True

        if changed:
            metadata["entity_normalization"] = {
                "canonical_entity_id": (
                    canonical_entity.get("id") if canonical_entity else None
                ),
                "canonical_display_name": (
                    canonical_entity.get("display_name") if canonical_entity else None
                ),
                "obsolete_aliases": sorted(obsolete_names),
                "correction_confidence": 0.9,
            }
            updated["metadata"] = metadata

        return EntityNormalizationResult(
            payload=updated,
            canonical_entity=canonical_entity,
            obsolete_names=obsolete_names,
            changed=changed,
        )

    def correction_pairs_from_text(
        self,
        text: Any,
        *,
        entity_type: Optional[str] = None,
    ) -> list[EntityCorrection]:
        cleaned = _clean_text(text)
        if not cleaned:
            return []
        pairs: list[EntityCorrection] = []
        patterns = (
            r"\bnot\s+([A-Za-z0-9][A-Za-z0-9 ._-]{0,40}?),\s*(?:it'?s|its|actually|the real name is|real name is)\s+([A-Za-z0-9][A-Za-z0-9 ._-]{0,40})",
            r"\b([A-Za-z0-9][A-Za-z0-9 ._-]{0,40}?)\s+was\s+wrong[,; ]+(?:it'?s|its|actually|the real name is|real name is)\s+([A-Za-z0-9][A-Za-z0-9 ._-]{0,40})",
            r"\bmerge\s+([A-Za-z0-9][A-Za-z0-9 ._-]{0,40}?)\s+into\s+([A-Za-z0-9][A-Za-z0-9 ._-]{0,40})",
            r"\bdelete\s+(?:any\s+)?mentions?\s+of\s+([A-Za-z0-9][A-Za-z0-9 ._-]{0,40}?)\s*,?\s*(?:the\s+)?(?:real|correct)\s+name\s+(?:is|are)\s+([A-Za-z0-9][A-Za-z0-9 ._-]{0,40})",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, cleaned, flags=re.I):
                correction = self.apply_user_correction(
                    _trim_correction_value(match.group(1)),
                    _trim_correction_value(match.group(2)),
                    entity_type,
                )
                if correction.old_key and correction.new_key:
                    pairs.append(correction)
        return pairs

    def _detect_alias_entity(
        self,
        values: Iterable[str],
        known_entities: Iterable[dict[str, Any]],
        *,
        entity_type: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        keys = {normalize_entity_key(value) for value in values if _clean_text(value)}
        keys.discard("")
        if not keys:
            return None
        for entity in known_entities:
            if entity_type and entity.get("entity_type") != entity_type:
                continue
            if keys & _entity_keys(entity, include_aliases=True):
                return entity
        return None


def normalize_entity_key(value: Any) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    normalized = re.sub(r"[^a-z0-9$]+", " ", cleaned.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _dedupe_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _obsolete_names_from_payload(payload: dict[str, Any]) -> set[str]:
    metadata = payload.get("metadata") or {}
    names = set()
    for key in OBSOLETE_METADATA_KEYS:
        raw_value = metadata.get(key)
        if isinstance(raw_value, list):
            names.update(normalize_entity_key(value) for value in raw_value)
        elif raw_value:
            names.add(normalize_entity_key(raw_value))
    return {name for name in names if name}


def _obsolete_names_for_entity(entity: dict[str, Any]) -> set[str]:
    names = _obsolete_names_from_payload(entity)
    metadata = entity.get("metadata") or {}
    person_correction = metadata.get("person_correction")
    if isinstance(person_correction, dict):
        raw_value = person_correction.get("wrong_names")
        if isinstance(raw_value, list):
            names.update(normalize_entity_key(value) for value in raw_value)
        elif raw_value:
            names.add(normalize_entity_key(raw_value))
    canonical_id = metadata.get("canonical_entity_id")
    if canonical_id and canonical_id != entity.get("id"):
        names.update(_entity_keys(entity, include_aliases=True))
    return {name for name in names if name}


def _entity_keys(entity: dict[str, Any], *, include_aliases: bool) -> set[str]:
    values = [entity.get("normalized_name"), entity.get("display_name")]
    if include_aliases:
        values.extend(entity.get("aliases") or [])
    return {normalize_entity_key(value) for value in values if _clean_text(value)}


def _replace_obsolete_name_refs(value: Any, replacements: dict[str, str]) -> Any:
    if value is None or not isinstance(value, str):
        return value
    updated = value
    for obsolete, canonical in sorted(
        replacements.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if not obsolete:
            continue
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(obsolete)}(?![A-Za-z0-9])",
            flags=re.I,
        )
        updated = pattern.sub(canonical, updated)
    return updated


def _trim_correction_value(value: str) -> str:
    value = re.sub(r"\b(?:and|or|too|also)$", "", value.strip(), flags=re.I).strip()
    return re.sub(r"[.!?,;:]+$", "", value).strip()
