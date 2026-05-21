from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

from app.services.entity_normalization_service import EntityNormalizationService


CORRECTION_VERSION = 1
HIGH_IMPACT_RECORD_THRESHOLD = 5


class CorrectionIntentType(str, Enum):
    REPLACE_VALUE = "replace_value"
    REMOVE_OBSOLETE = "remove_obsolete"
    MERGE_ITEMS = "merge_items"
    MOVE_UNDER_PARENT = "move_under_parent"
    DOWNGRADE_PLAN_TO_TASK = "downgrade_plan_to_task"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CorrectionIntent:
    intent_type: CorrectionIntentType
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    target_hint: Optional[str] = None
    confidence: float = 0.75
    requires_confirmation: bool = False


@dataclass
class CorrectionAffectedRecord:
    table: str
    id: str
    action: str
    title: Optional[str] = None
    previous: dict[str, Any] = field(default_factory=dict)
    updated: Optional[dict[str, Any]] = None


@dataclass
class CorrectionReport:
    intent: CorrectionIntent
    applied: bool = False
    requires_confirmation: bool = False
    affected_records: list[CorrectionAffectedRecord] = field(default_factory=list)
    corrections: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    confirmation_payload: Optional[dict[str, Any]] = None
    verification_stale_terms: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": {
                "intent_type": self.intent.intent_type.value,
                "old_value": self.intent.old_value,
                "new_value": self.intent.new_value,
                "target_hint": self.intent.target_hint,
                "confidence": self.intent.confidence,
                "requires_confirmation": self.intent.requires_confirmation,
            },
            "applied": self.applied,
            "requires_confirmation": self.requires_confirmation,
            "affected_records": [
                {
                    "table": record.table,
                    "id": record.id,
                    "action": record.action,
                    "title": record.title,
                }
                for record in self.affected_records
            ],
            "corrections": self.corrections,
            "errors": self.errors,
            "confirmation_payload": self.confirmation_payload,
            "verification_stale_terms": self.verification_stale_terms,
        }


class MemoryCorrectionRepository(Protocol):
    async def list_long_term_memory(
        self,
        limit: int = 50,
        memory_type: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        pass

    async def update_long_term_memory(self, memory_id: str, **updates: object) -> Optional[dict]:
        pass

    async def deactivate_long_term_memory(self, memory_id: str) -> bool:
        pass

    async def list_entities(
        self,
        limit: int = 50,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        normalized_name: Optional[str] = None,
    ) -> list[dict]:
        pass

    async def update_entity(self, entity_id: str, **updates: object) -> Optional[dict]:
        pass

    async def deactivate_entity(self, entity_id: str) -> bool:
        pass

    async def create_memory_correction(self, correction: dict) -> dict:
        pass


@dataclass(frozen=True)
class _TableSpec:
    table: str
    list_method: str
    update_method: str
    deactivate_method: str
    text_fields: tuple[str, ...]
    correction_type: str


TABLE_SPECS = (
    _TableSpec(
        table="long_term_memory",
        list_method="list_long_term_memory",
        update_method="update_long_term_memory",
        deactivate_method="deactivate_long_term_memory",
        text_fields=("content",),
        correction_type="other",
    ),
    _TableSpec(
        table="entities",
        list_method="list_entities",
        update_method="update_entity",
        deactivate_method="deactivate_entity",
        text_fields=("display_name", "normalized_name", "aliases", "relationship", "summary"),
        correction_type="entity_name",
    ),
    _TableSpec(
        table="entity_events",
        list_method="list_entity_events",
        update_method="update_entity_event",
        deactivate_method="deactivate_entity_event",
        text_fields=("title", "content"),
        correction_type="entity_relationship",
    ),
    _TableSpec(
        table="personal_rules",
        list_method="list_personal_rules",
        update_method="update_personal_rule",
        deactivate_method="deactivate_personal_rule",
        text_fields=("title", "rule_text", "trigger_keywords"),
        correction_type="rule_detail",
    ),
    _TableSpec(
        table="plans",
        list_method="list_plans",
        update_method="update_plan",
        deactivate_method="deactivate_plan",
        text_fields=("title", "description", "desired_outcome"),
        correction_type="plan_detail",
    ),
    _TableSpec(
        table="plan_milestones",
        list_method="list_plan_milestones",
        update_method="update_plan_milestone",
        deactivate_method="deactivate_plan_milestone",
        text_fields=("title", "description"),
        correction_type="plan_detail",
    ),
    _TableSpec(
        table="commitments",
        list_method="list_commitments",
        update_method="update_commitment",
        deactivate_method="deactivate_commitment",
        text_fields=("title", "commitment_text"),
        correction_type="commitment_detail",
    ),
)


class MemoryCorrectionService:
    """Detects and applies explicit memory corrections across structured records."""

    def __init__(
        self,
        memory_service: MemoryCorrectionRepository,
        *,
        scan_limit: int = 250,
    ) -> None:
        self.memory_service = memory_service
        self.scan_limit = scan_limit
        self.entity_normalization_service = EntityNormalizationService()

    def detect_correction_intent(self, text: str) -> CorrectionIntent:
        cleaned = _clean(text)
        lowered = cleaned.lower()
        if not cleaned:
            return CorrectionIntent(CorrectionIntentType.UNKNOWN, confidence=0)

        removal = re.search(
            r"\b(?:delete|remove|archive|drop)\s+(?:any\s+)?(?:mention|mentions|memory|memories|record|records)?\s*(?:of|about|for)?\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if removal:
            return CorrectionIntent(
                CorrectionIntentType.REMOVE_OBSOLETE,
                old_value=_trim(removal.group(1)),
                new_value="[archived]",
                confidence=0.9,
            )

        if re.search(r"\bnot\s+a\s+plan\b.*\b(?:task|commitment|checklist)\b", lowered):
            return CorrectionIntent(
                CorrectionIntentType.DOWNGRADE_PLAN_TO_TASK,
                target_hint=cleaned,
                confidence=0.72,
                requires_confirmation=True,
            )

        direct_correction = re.search(
            r"\bnot\s+(.+?)\s*,?\s+(?:it\s+is|it's|actually|the\s+real\s+name\s+is)\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if direct_correction:
            return CorrectionIntent(
                CorrectionIntentType.REPLACE_VALUE,
                old_value=_trim(direct_correction.group(1)),
                new_value=_trim(direct_correction.group(2)),
                confidence=0.9,
            )

        pairs = self.entity_normalization_service.correction_pairs_from_text(cleaned)
        if pairs:
            pair = pairs[0]
            return CorrectionIntent(
                CorrectionIntentType.REPLACE_VALUE,
                old_value=pair.old_value,
                new_value=pair.new_value,
                confidence=pair.confidence,
            )

        replace = re.search(
            r"\b(?:replace|rename|change)\s+(.+?)\s+(?:with|to)\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if replace:
            return CorrectionIntent(
                CorrectionIntentType.REPLACE_VALUE,
                old_value=_trim(replace.group(1)),
                new_value=_trim(replace.group(2)),
                confidence=0.86,
            )

        if re.search(r"\bmerge\b.*\bplans?\b|\bplans?\b.*\bmerge\b", lowered):
            return CorrectionIntent(
                CorrectionIntentType.MERGE_ITEMS,
                target_hint=cleaned,
                confidence=0.7,
                requires_confirmation=True,
            )

        move = re.search(
            r"\b(?:under|inside|into)\s+(?:the\s+)?(.+?)\s+plan\b",
            cleaned,
            flags=re.IGNORECASE,
        )
        if move:
            return CorrectionIntent(
                CorrectionIntentType.MOVE_UNDER_PARENT,
                target_hint=_trim(move.group(1)),
                confidence=0.72,
                requires_confirmation=True,
            )

        return CorrectionIntent(CorrectionIntentType.UNKNOWN, confidence=0.2)

    async def apply_correction(
        self,
        text: str,
        *,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        force: bool = False,
    ) -> CorrectionReport:
        intent = self.detect_correction_intent(text)
        report = CorrectionReport(intent=intent)
        if intent.intent_type == CorrectionIntentType.UNKNOWN:
            person_affected = await self._apply_person_fact_correction(text)
            if not person_affected:
                return report
            report.affected_records = person_affected
            report.applied = True
            report.verification_stale_terms = _person_fact_stale_terms(text)
            for affected_record in person_affected:
                correction = await self._record_correction(
                    intent,
                    affected_record,
                    source_conversation_id=source_conversation_id,
                    source_message_id=source_message_id,
                )
                if correction:
                    report.corrections.append(correction)
            return report

        if intent.requires_confirmation and not force:
            report.requires_confirmation = True
            report.confirmation_payload = _confirmation_payload(intent)
            return report

        preview_count = await self._preview_affected_count(intent)
        if preview_count > HIGH_IMPACT_RECORD_THRESHOLD and not force:
            report.requires_confirmation = True
            report.confirmation_payload = {
                **_confirmation_payload(intent),
                "affected_count": preview_count,
            }
            return report

        if intent.intent_type == CorrectionIntentType.REMOVE_OBSOLETE:
            affected = await self._archive_records_matching(intent.old_value or "")
        elif intent.intent_type == CorrectionIntentType.REPLACE_VALUE:
            affected = await self._replace_value(intent.old_value or "", intent.new_value or "")
        else:
            report.requires_confirmation = True
            report.confirmation_payload = _confirmation_payload(intent)
            return report

        report.affected_records = affected
        report.applied = bool(affected)
        for affected_record in affected:
            correction = await self._record_correction(
                intent,
                affected_record,
                source_conversation_id=source_conversation_id,
                source_message_id=source_message_id,
            )
            if correction:
                report.corrections.append(correction)
        return report

    async def _apply_person_fact_correction(
        self,
        text: str,
    ) -> list[CorrectionAffectedRecord]:
        affected: list[CorrectionAffectedRecord] = []
        entities = await self._safe_list(_spec_for_table("entities"))
        if not entities:
            return affected

        for entity in entities:
            updates = _person_fact_entity_updates(entity, text)
            if not updates:
                continue
            updated = await self._safe_update(
                _spec_for_table("entities"),
                str(entity["id"]),
                updates,
            )
            if updated is None:
                continue
            affected.append(
                CorrectionAffectedRecord(
                    table="entities",
                    id=str(entity["id"]),
                    action="updated",
                    title=_record_title(entity),
                    previous=entity,
                    updated=updated,
                )
            )

        negative_fired = _negative_fired_fact(text)
        if negative_fired:
            affected.extend(
                await self._replace_person_stale_fired_fact(
                    person_name=negative_fired["name"],
                    replacement=negative_fired["replacement"],
                )
            )
        return _dedupe_affected(affected)

    async def _replace_person_stale_fired_fact(
        self,
        *,
        person_name: str,
        replacement: str,
    ) -> list[CorrectionAffectedRecord]:
        affected: list[CorrectionAffectedRecord] = []
        person_key = _normalize_key(person_name)
        if not person_key or not replacement:
            return affected

        for spec in TABLE_SPECS:
            records = await self._safe_list(spec)
            for record in records:
                if not _record_contains(record, spec, person_name):
                    continue
                updates = _replace_fired_fact_updates(record, spec, replacement)
                if not updates:
                    continue
                updated = await self._safe_update(spec, str(record["id"]), updates)
                if updated is None:
                    continue
                affected.append(
                    CorrectionAffectedRecord(
                        table=spec.table,
                        id=str(record["id"]),
                        action="updated",
                        title=_record_title(record),
                        previous=record,
                        updated=updated,
                    )
                )
        return affected

    async def _preview_affected_count(self, intent: CorrectionIntent) -> int:
        if intent.intent_type not in {
            CorrectionIntentType.REMOVE_OBSOLETE,
            CorrectionIntentType.REPLACE_VALUE,
        }:
            return 0
        count = 0
        for spec in TABLE_SPECS:
            records = await self._safe_list(spec)
            for record in records:
                if intent.intent_type == CorrectionIntentType.REMOVE_OBSOLETE:
                    if _record_contains(record, spec, intent.old_value or ""):
                        count += 1
                elif _replacement_updates(
                    record,
                    spec,
                    intent.old_value or "",
                    intent.new_value or "",
                ):
                    count += 1
        return count

    async def _replace_value(
        self,
        old_value: str,
        new_value: str,
    ) -> list[CorrectionAffectedRecord]:
        if not old_value or not new_value:
            return []
        affected: list[CorrectionAffectedRecord] = []
        for spec in TABLE_SPECS:
            records = await self._safe_list(spec)
            for record in records:
                updates = _replacement_updates(record, spec, old_value, new_value)
                if not updates:
                    continue
                updated = await self._safe_update(spec, str(record["id"]), updates)
                if updated is None:
                    continue
                affected.append(
                    CorrectionAffectedRecord(
                        table=spec.table,
                        id=str(record["id"]),
                        action="updated",
                        title=_record_title(record),
                        previous=record,
                        updated=updated,
                    )
                )

        affected.extend(await self._archive_superseded_entities(old_value, new_value))
        return _dedupe_affected(affected)

    async def _archive_records_matching(
        self,
        old_value: str,
    ) -> list[CorrectionAffectedRecord]:
        if not old_value:
            return []
        affected: list[CorrectionAffectedRecord] = []
        for spec in TABLE_SPECS:
            records = await self._safe_list(spec)
            for record in records:
                if not _record_contains(record, spec, old_value):
                    continue
                archived = await self._safe_archive(spec, str(record["id"]))
                if not archived:
                    continue
                affected.append(
                    CorrectionAffectedRecord(
                        table=spec.table,
                        id=str(record["id"]),
                        action="archived",
                        title=_record_title(record),
                        previous=record,
                    )
                )
        return affected

    async def _archive_superseded_entities(
        self,
        old_value: str,
        new_value: str,
    ) -> list[CorrectionAffectedRecord]:
        old_key = _normalize_key(old_value)
        new_key = _normalize_key(new_value)
        if not old_key or not new_key or old_key == new_key:
            return []
        entities = await self._safe_list(_spec_for_table("entities"))
        canonical = next(
            (
                entity
                for entity in entities
                if _normalize_key(entity.get("display_name")) == new_key
                or _normalize_key(entity.get("normalized_name")) == new_key
            ),
            None,
        )
        if canonical is None:
            return []

        affected: list[CorrectionAffectedRecord] = []
        for entity in entities:
            if str(entity.get("id")) == str(canonical.get("id")):
                continue
            names = [
                entity.get("display_name"),
                entity.get("normalized_name"),
                *(entity.get("aliases") or []),
            ]
            if old_key not in {_normalize_key(name) for name in names}:
                continue
            archived = await self._safe_archive(_spec_for_table("entities"), str(entity["id"]))
            if archived:
                affected.append(
                    CorrectionAffectedRecord(
                        table="entities",
                        id=str(entity["id"]),
                        action="archived",
                        title=_record_title(entity),
                        previous=entity,
                    )
                )

        metadata = dict(canonical.get("metadata") or {})
        obsolete = set(metadata.get("obsolete_aliases") or [])
        obsolete.add(old_key)
        metadata["obsolete_aliases"] = sorted(obsolete)
        metadata["correction_confidence"] = 0.9
        updated_canonical = await self._safe_update(
            _spec_for_table("entities"),
            str(canonical["id"]),
            {"metadata": metadata},
        )
        if updated_canonical:
            affected.append(
                CorrectionAffectedRecord(
                    table="entities",
                    id=str(canonical["id"]),
                    action="updated",
                    title=_record_title(canonical),
                    previous=canonical,
                    updated=updated_canonical,
                )
            )
        return affected

    async def _record_correction(
        self,
        intent: CorrectionIntent,
        affected_record: CorrectionAffectedRecord,
        *,
        source_conversation_id: Optional[str],
        source_message_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        create_correction = getattr(self.memory_service, "create_memory_correction", None)
        if create_correction is None:
            return None
        payload = {
            "correction_type": _correction_type_for_table(affected_record.table, intent),
            "old_value": intent.old_value or affected_record.title,
            "new_value": intent.new_value or "[archived]",
            "target_table": affected_record.table,
            "target_id": affected_record.id,
            "source_conversation_id": source_conversation_id,
            "source_message_id": source_message_id,
            "applied": True,
            "confidence": intent.confidence,
            "metadata": {
                "correction_version": CORRECTION_VERSION,
                "intent_type": intent.intent_type.value,
                "action": affected_record.action,
                "affected_title": affected_record.title,
            },
        }
        try:
            return await create_correction(payload)
        except Exception:
            return None

    async def _safe_list(self, spec: _TableSpec) -> list[dict[str, Any]]:
        method = getattr(self.memory_service, spec.list_method, None)
        if method is None:
            return []
        try:
            return await method(active=True, limit=self.scan_limit)
        except TypeError:
            try:
                return await method(limit=self.scan_limit)
            except Exception:
                return []
        except Exception:
            return []

    async def _safe_update(
        self,
        spec: _TableSpec,
        record_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        method = getattr(self.memory_service, spec.update_method, None)
        if method is None:
            return None
        try:
            return await method(record_id, **updates)
        except Exception:
            return None

    async def _safe_archive(self, spec: _TableSpec, record_id: str) -> bool:
        method = getattr(self.memory_service, spec.deactivate_method, None)
        if method is None:
            return False
        try:
            return bool(await method(record_id))
        except Exception:
            return False


def _replacement_updates(
    record: dict[str, Any],
    spec: _TableSpec,
    old_value: str,
    new_value: str,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field_name in spec.text_fields:
        value = record.get(field_name)
        replaced = _replace_value(value, old_value, new_value)
        if replaced != value:
            updates[field_name] = replaced
    if updates:
        metadata = dict(record.get("metadata") or {})
        metadata.update(
            {
                "correction_version": CORRECTION_VERSION,
                "correction_action": "replace_value",
                "old_value": old_value,
                "new_value": new_value,
            }
        )
        updates["metadata"] = metadata
    return updates


def _person_fact_entity_updates(record: dict[str, Any], text: str) -> dict[str, Any]:
    names = [
        record.get("display_name"),
        record.get("normalized_name"),
        *(record.get("aliases") or []),
    ]
    sentences = _sentences(text)
    summary_parts: list[str] = []
    relationship = None
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        pattern = re.compile(
            rf"\b{re.escape(name.strip())}\s+(?:is|was)\s+(.+)$",
            flags=re.IGNORECASE,
        )
        for sentence in sentences:
            match = pattern.search(sentence)
            if not match:
                continue
            fact = _trim(match.group(1))
            if fact:
                summary_parts.append(_capitalize_sentence(fact))
                if relationship is None:
                    relationship = _short_relationship(fact)

        quit_pattern = re.compile(
            rf"\b{re.escape(name.strip())}\s+quit\s+([^.!?]+)",
            flags=re.IGNORECASE,
        )
        for sentence in sentences:
            match = quit_pattern.search(sentence)
            if match:
                summary_parts.append(
                    _capitalize_sentence(f"{name.strip()} quit {_trim(match.group(1))}")
                )

    if not summary_parts:
        return {}

    summary = _join_unique_sentences(summary_parts)
    updates: dict[str, Any] = {
        "summary": summary,
        "metadata": {
            **(record.get("metadata") or {}),
            "correction_version": CORRECTION_VERSION,
            "correction_action": "person_fact_update",
        },
    }
    if relationship:
        updates["relationship"] = relationship
    return updates


def _negative_fired_fact(text: str) -> Optional[dict[str, str]]:
    for sentence in _sentences(text):
        negative = re.search(
            r"\b([A-Z][a-z]+)\s+(?:was\s+)?not\s+fired\b",
            sentence,
        )
        if not negative:
            continue
        name = negative.group(1)
        replacement = _quit_fact_for_person(text, name)
        if replacement:
            return {"name": name, "replacement": replacement}
    return None


def _quit_fact_for_person(text: str, name: str) -> str | None:
    pattern = re.compile(
        rf"\b{re.escape(name)}\s+quit\s+([^.!?]+)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    return f"{name} quit {_trim(match.group(1))}"


def _replace_fired_fact_updates(
    record: dict[str, Any],
    spec: _TableSpec,
    replacement: str,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field_name in spec.text_fields:
        value = record.get(field_name)
        replaced = _replace_fired_fact(value, replacement)
        if replaced != value:
            updates[field_name] = replaced
    if updates:
        updates["metadata"] = {
            **(record.get("metadata") or {}),
            "correction_version": CORRECTION_VERSION,
            "correction_action": "person_negative_fact_replace",
            "new_value": replacement,
        }
    return updates


def _replace_fired_fact(value: Any, replacement: str) -> Any:
    if isinstance(value, list):
        return [_replace_fired_fact(item, replacement) for item in value]
    if not isinstance(value, str):
        return value
    if "fired" not in value.casefold():
        return value
    patterns = [
        r"\bgot\s+fired(?:\s+(?:at|in|on)\s+the\s+beginning\s+of\s+this\s+year)?",
        r"\bwas\s+fired(?:\s+(?:at|in|on)\s+the\s+beginning\s+of\s+this\s+year)?",
    ]
    replaced = value
    for pattern in patterns:
        replaced = re.sub(pattern, replacement, replaced, flags=re.IGNORECASE)
    return replaced


def _person_fact_stale_terms(text: str) -> list[str]:
    negative = _negative_fired_fact(text)
    if not negative:
        return []
    return [f"{negative['name']} got fired", f"{negative['name']} was fired"]


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"[.!?]+", text)
        if sentence.strip()
    ]


def _capitalize_sentence(text: str) -> str:
    text = _trim(text)
    return text[:1].upper() + text[1:] if text else text


def _short_relationship(fact: str) -> str:
    lowered = fact.casefold()
    if "friend" in lowered:
        return "friend"
    if "supervisor" in lowered:
        return "kitchen supervisor" if "kitchen" in lowered else "supervisor"
    return fact.split(",", 1)[0][:120]


def _join_unique_sentences(parts: list[str]) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        key = _normalize_key(part)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(part)
    return ". ".join(result)


def _replace_value(value: Any, old_value: str, new_value: str) -> Any:
    if isinstance(value, list):
        return [_replace_value(item, old_value, new_value) for item in value]
    if not isinstance(value, str):
        return value
    pattern = re.compile(re.escape(old_value), re.IGNORECASE)
    return pattern.sub(new_value, value)


def _record_contains(record: dict[str, Any], spec: _TableSpec, value: str) -> bool:
    value_key = _normalize_key(value)
    if not value_key:
        return False
    for field_name in spec.text_fields:
        if value_key in _normalize_key(record.get(field_name)):
            return True
    return False


def _correction_type_for_table(table: str, intent: CorrectionIntent) -> str:
    if intent.intent_type == CorrectionIntentType.REPLACE_VALUE and table == "entities":
        return "entity_name"
    return _spec_for_table(table).correction_type


def _spec_for_table(table: str) -> _TableSpec:
    for spec in TABLE_SPECS:
        if spec.table == table:
            return spec
    raise KeyError(table)


def _dedupe_affected(records: list[CorrectionAffectedRecord]) -> list[CorrectionAffectedRecord]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[CorrectionAffectedRecord] = []
    for record in records:
        key = (record.table, record.id, record.action)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _confirmation_payload(intent: CorrectionIntent) -> dict[str, Any]:
    return {
        "intent_type": intent.intent_type.value,
        "old_value": intent.old_value,
        "new_value": intent.new_value,
        "target_hint": intent.target_hint,
        "reason": "Correction is ambiguous or may archive multiple active records.",
    }


def _record_title(record: dict[str, Any]) -> Optional[str]:
    return (
        record.get("title")
        or record.get("display_name")
        or record.get("content")
        or record.get("commitment_text")
    )


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _trim(value: str) -> str:
    value = _clean(value)
    value = re.sub(r"[.!?]+$", "", value).strip()
    return value.strip("\"'")


def _normalize_key(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
