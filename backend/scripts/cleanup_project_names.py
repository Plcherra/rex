from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.http_client import shutdown_http_client, startup_http_client
from app.services.memory_service import SupabaseMemoryService


CLEANUP_VERSION = 1

TEXT_REPLACEMENTS = (
    (re.compile(r"\becho\s*task\b", re.IGNORECASE), "EchoDesk"),
    (re.compile(r"\bechotask\b", re.IGNORECASE), "EchoDesk"),
    (re.compile(r"\bflow\s*(?:first|forte|force)\b", re.IGNORECASE), "FlowForce"),
    (re.compile(r"\bflow\b", re.IGNORECASE), "FlowForce"),
)

WRONG_PROJECT_TARGETS = {
    "echo task": "EchoDesk",
    "echotask": "EchoDesk",
    "flow": "FlowForce",
    "flow echotask": "EchoDesk and FlowForce",
    "flow first": "FlowForce",
    "flowfirst": "FlowForce",
    "flow forte": "FlowForce",
    "flowforte": "FlowForce",
    "flowforce echodesk": "EchoDesk and FlowForce",
    "echodesk flowforce": "EchoDesk and FlowForce",
}


@dataclass
class ProjectNameCleanupReport:
    dry_run: bool
    scanned: dict[str, int] = field(default_factory=dict)
    updated: list[dict[str, Any]] = field(default_factory=list)
    archived_entities: list[dict[str, Any]] = field(default_factory=list)
    created_entities: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "scanned": self.scanned,
            "updated": self.updated,
            "archived_entities": self.archived_entities,
            "created_entities": self.created_entities,
            "errors": self.errors,
        }


async def cleanup_project_names(
    memory_service: SupabaseMemoryService,
    *,
    apply: bool = False,
    limit: int = 500,
) -> ProjectNameCleanupReport:
    report = ProjectNameCleanupReport(dry_run=not apply)

    if apply:
        await _ensure_canonical_project(memory_service, report, "EchoDesk")
        await _ensure_canonical_project(memory_service, report, "FlowForce")

    await _cleanup_entities(memory_service, report, apply=apply, limit=limit)
    await _cleanup_records(
        memory_service,
        report,
        table="long_term_memory",
        list_method="list_long_term_memory",
        update_method="update_long_term_memory",
        fields=("content", "metadata"),
        apply=apply,
        limit=limit,
    )
    await _cleanup_records(
        memory_service,
        report,
        table="plans",
        list_method="list_plans",
        update_method="update_plan",
        fields=("title", "description", "desired_outcome", "metadata"),
        apply=apply,
        limit=limit,
    )
    await _cleanup_records(
        memory_service,
        report,
        table="plan_milestones",
        list_method="list_plan_milestones",
        update_method="update_plan_milestone",
        fields=("title", "description", "metadata"),
        apply=apply,
        limit=limit,
    )
    await _cleanup_records(
        memory_service,
        report,
        table="personal_rules",
        list_method="list_personal_rules",
        update_method="update_personal_rule",
        fields=("title", "rule_text", "trigger_keywords", "metadata"),
        apply=apply,
        limit=limit,
    )
    await _cleanup_records(
        memory_service,
        report,
        table="commitments",
        list_method="list_commitments",
        update_method="update_commitment",
        fields=("title", "commitment_text", "metadata"),
        apply=apply,
        limit=limit,
    )
    return report


async def _ensure_canonical_project(
    memory_service: SupabaseMemoryService,
    report: ProjectNameCleanupReport,
    display_name: str,
) -> None:
    normalized_name = _normalize(display_name)
    existing = await memory_service.list_entities(
        entity_type="project",
        normalized_name=normalized_name,
        active=True,
        limit=1,
    )
    if existing:
        return
    entity = await memory_service.create_entity(
        {
            "entity_type": "project",
            "display_name": display_name,
            "normalized_name": normalized_name,
            "aliases": [],
            "relationship": "user's active project",
            "summary": f"{display_name} is one of the user's active projects.",
            "importance": 4,
            "status": "active",
            "active": True,
            "metadata": {
                "cleanup_reason": "project_name_correction",
                "cleanup_version": CLEANUP_VERSION,
            },
        }
    )
    report.created_entities.append(_preview("entities", entity))


async def _cleanup_entities(
    memory_service: SupabaseMemoryService,
    report: ProjectNameCleanupReport,
    *,
    apply: bool,
    limit: int,
) -> None:
    entities = await memory_service.list_entities(active=True, limit=limit)
    report.scanned["entities"] = len(entities)

    for entity in entities:
        entity_id = str(entity.get("id") or "")
        target = _wrong_project_target(entity)
        if target:
            if apply:
                try:
                    await memory_service.update_entity(
                        entity_id,
                        active=False,
                        status="inactive",
                        metadata={
                            **(entity.get("metadata") or {}),
                            "cleanup_reason": "project_name_correction",
                            "cleanup_version": CLEANUP_VERSION,
                            "corrected_to": target,
                        },
                    )
                except Exception as error:  # pragma: no cover - CLI safety net
                    report.errors.append(
                        {"table": "entities", "id": entity_id, "error": str(error)}
                    )
                    continue
            report.archived_entities.append(
                {
                    **_preview("entities", entity),
                    "corrected_to": target,
                }
            )
            continue

        updates = _clean_entity_updates(entity)
        if not updates:
            continue
        if apply:
            try:
                await memory_service.update_entity(entity_id, **updates)
            except Exception as error:  # pragma: no cover - CLI safety net
                report.errors.append(
                    {"table": "entities", "id": entity_id, "error": str(error)}
                )
                continue
        report.updated.append(_update_preview("entities", entity, updates))


async def _cleanup_records(
    memory_service: SupabaseMemoryService,
    report: ProjectNameCleanupReport,
    *,
    table: str,
    list_method: str,
    update_method: str,
    fields: tuple[str, ...],
    apply: bool,
    limit: int,
) -> None:
    records = await getattr(memory_service, list_method)(active=True, limit=limit)
    report.scanned[table] = len(records)

    for record in records:
        updates = _changed_fields(record, fields)
        if not updates:
            continue
        record_id = str(record.get("id") or "")
        if apply:
            try:
                await getattr(memory_service, update_method)(record_id, **updates)
            except Exception as error:  # pragma: no cover - CLI safety net
                report.errors.append(
                    {"table": table, "id": record_id, "error": str(error)}
                )
                continue
        report.updated.append(_update_preview(table, record, updates))


def _clean_entity_updates(entity: dict[str, Any]) -> dict[str, Any]:
    updates = _changed_fields(
        entity,
        ("display_name", "relationship", "summary", "metadata"),
    )
    if "display_name" in updates:
        updates["normalized_name"] = _normalize(updates["display_name"])
    elif "normalized_name" in entity:
        normalized_name = _normalize(_replace_text(entity.get("normalized_name")))
        if normalized_name != entity.get("normalized_name"):
            updates["normalized_name"] = normalized_name

    aliases = entity.get("aliases") or []
    if isinstance(aliases, list):
        cleaned_aliases = [
            _replace_text(alias)
            for alias in aliases
            if not _wrong_project_target({"display_name": alias, "entity_type": "project"})
        ]
        cleaned_aliases = _dedupe_preserving_order(cleaned_aliases)
        if cleaned_aliases != aliases:
            updates["aliases"] = cleaned_aliases
    return updates


def _changed_fields(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field_name in fields:
        if field_name not in record:
            continue
        cleaned = _replace_value(record.get(field_name))
        if cleaned != record.get(field_name):
            updates[field_name] = cleaned
    return updates


def _replace_value(value: Any) -> Any:
    if isinstance(value, str):
        return _replace_text(value)
    if isinstance(value, list):
        return [_replace_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_value(item) for key, item in value.items()}
    return value


def _replace_text(value: Any) -> str:
    text = str(value)
    for pattern, replacement in TEXT_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return _tidy_project_names(text)


def _tidy_project_names(text: str) -> str:
    text = re.sub(
        r"\bFlowForce,\s*EchoDesk,\s*(?:and\s*)?FlowForce\b",
        "EchoDesk, FlowForce",
        text,
    )
    text = re.sub(
        r"\bEchoDesk,\s*FlowForce,\s*(?:and\s*)?FlowForce\b",
        "EchoDesk, FlowForce",
        text,
    )
    text = re.sub(r"\bFlowForce,\s*FlowForce\b", "FlowForce", text)
    text = re.sub(r"\bEchoDesk,\s*EchoDesk\b", "EchoDesk", text)
    return text


def _wrong_project_target(entity: dict[str, Any]) -> str | None:
    if entity.get("entity_type") and entity.get("entity_type") != "project":
        return None
    for field_name in ("normalized_name", "display_name"):
        key = _normalize(entity.get(field_name))
        if key in WRONG_PROJECT_TARGETS:
            return WRONG_PROJECT_TARGETS[key]
    return None


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = _normalize(value)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _update_preview(
    table: str,
    record: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    return {
        "table": table,
        "id": record.get("id"),
        "title": _record_title(record),
        "fields": sorted(updates),
    }


def _preview(table: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "table": table,
        "id": record.get("id"),
        "title": _record_title(record),
    }


def _record_title(record: dict[str, Any]) -> str | None:
    for field_name in ("title", "display_name", "content", "rule_text"):
        value = record.get(field_name)
        if value:
            return str(value)[:120]
    return None


def _normalize(value: Any) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean stale project names from active structured memory."
    )
    parser.add_argument("--apply", action="store_true", help="Apply the cleanup.")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    await startup_http_client()
    try:
        report = await cleanup_project_names(
            SupabaseMemoryService(),
            apply=args.apply,
            limit=args.limit,
        )
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    finally:
        await shutdown_http_client()


if __name__ == "__main__":
    asyncio.run(_main())
