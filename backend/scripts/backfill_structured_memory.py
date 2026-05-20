from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.models.entity import EntityCreateRequest
from app.models.personal_rule import PersonalRuleCreateRequest
from app.models.plan import PlanCreateRequest
from app.services.entity_service import (
    EntityService,
    _correction_wrong_names as _entity_correction_wrong_names,
)
from app.services.http_client import shutdown_http_client, startup_http_client
from app.services.memory_service import SupabaseMemoryService
from app.services.plan_service import PlanService
from app.services.rule_service import RuleService


BACKFILL_VERSION = 1
AMBIGUOUS_PERSON_NAMES = {"ai", "al", "rex", "user"}
US_STATES = {
    "Alabama",
    "Alaska",
    "Arizona",
    "Arkansas",
    "California",
    "Colorado",
    "Connecticut",
    "Delaware",
    "Florida",
    "Georgia",
    "Hawaii",
    "Idaho",
    "Illinois",
    "Indiana",
    "Iowa",
    "Kansas",
    "Kentucky",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Michigan",
    "Minnesota",
    "Mississippi",
    "Missouri",
    "Montana",
    "Nebraska",
    "Nevada",
    "New Hampshire",
    "New Jersey",
    "New Mexico",
    "New York",
    "North Carolina",
    "North Dakota",
    "Ohio",
    "Oklahoma",
    "Oregon",
    "Pennsylvania",
    "Rhode Island",
    "South Carolina",
    "South Dakota",
    "Tennessee",
    "Texas",
    "Utah",
    "Vermont",
    "Virginia",
    "Washington",
    "West Virginia",
    "Wisconsin",
    "Wyoming",
}


@dataclass(frozen=True)
class BackfillCandidate:
    kind: str
    payload: dict[str, Any]
    link_key: str | None = None


@dataclass
class BackfillReport:
    dry_run: bool
    scanned: int = 0
    skipped: int = 0
    candidates: list[dict[str, Any]] = field(default_factory=list)
    upserted: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "scanned": self.scanned,
            "skipped": self.skipped,
            "candidates": self.candidates,
            "upserted": self.upserted,
            "errors": self.errors,
        }


async def backfill_structured_memory(
    memory_service: SupabaseMemoryService,
    *,
    apply: bool = False,
    limit: int = 100,
) -> BackfillReport:
    report = BackfillReport(dry_run=not apply)
    memories = await memory_service.list_long_term_memory(limit=limit, active=True)
    entity_service = EntityService(memory_service)
    plan_service = PlanService(memory_service)
    rule_service = RuleService(memory_service)

    for memory in memories:
        report.scanned += 1
        candidates = build_backfill_candidates(memory)
        if not candidates:
            report.skipped += 1
            continue

        report.candidates.extend(
            {
                "source_memory_id": memory.get("id"),
                "kind": candidate.kind,
                "payload": candidate.payload,
                "link_key": candidate.link_key,
            }
            for candidate in candidates
        )
        if not apply:
            continue

        linked_entities: dict[str, str] = {}
        linked_wrong_names: dict[str, set[str]] = {}
        for candidate in candidates:
            try:
                payload = dict(candidate.payload)
                if candidate.kind == "entity":
                    entity = await entity_service.create_entity(
                        EntityCreateRequest(**payload)
                    )
                    report.upserted.append(_upserted_row("entity", entity, memory))
                    if candidate.link_key:
                        linked_entities[candidate.link_key] = entity["id"]
                        wrong_names = _entity_correction_wrong_names(entity)
                        if wrong_names:
                            linked_wrong_names[candidate.link_key] = wrong_names
                elif candidate.kind == "plan":
                    if candidate.link_key and linked_entities.get(candidate.link_key):
                        payload["primary_entity_id"] = linked_entities[
                            candidate.link_key
                        ]
                    if candidate.link_key and linked_wrong_names.get(candidate.link_key):
                        payload["metadata"] = {
                            **(payload.get("metadata") or {}),
                            "wrong_names": sorted(
                                linked_wrong_names[candidate.link_key]
                            ),
                        }
                    plan = await plan_service.create_plan(PlanCreateRequest(**payload))
                    report.upserted.append(_upserted_row("plan", plan, memory))
                elif candidate.kind == "rule":
                    rule = await rule_service.create_rule(
                        PersonalRuleCreateRequest(**payload)
                    )
                    report.upserted.append(_upserted_row("rule", rule, memory))
            except Exception as error:  # pragma: no cover - CLI safety net
                report.errors.append(
                    {
                        "source_memory_id": str(memory.get("id")),
                        "kind": candidate.kind,
                        "error": str(error),
                    }
                )

    return report


def build_backfill_candidates(memory: dict[str, Any]) -> list[BackfillCandidate]:
    content = _clean_text(memory.get("content"))
    if not content:
        return []

    candidates: list[BackfillCandidate] = []
    source_metadata = _source_metadata(memory)

    place = _extract_us_state(content)
    if place:
        candidates.append(
            BackfillCandidate(
                kind="entity",
                payload={
                    "entity_type": "place",
                    "display_name": place,
                    "normalized_name": _normalize(place),
                    "summary": f"User is in {place}.",
                    "source_conversation_id": memory.get("source_conversation_id"),
                    "source_message_id": memory.get("source_message_id"),
                    "source_memory_id": memory.get("id"),
                    "importance": max(3, int(memory.get("importance") or 3)),
                    "metadata": source_metadata,
                },
            )
        )

    person_name = _extract_dating_person_name(content)
    if person_name:
        link_key = f"person:{_normalize(person_name)}"
        wrong_names = _entity_correction_wrong_names(
            {"metadata": source_metadata, "summary": content}
        )
        correction_metadata = dict(source_metadata)
        if wrong_names:
            correction_metadata["wrong_names"] = sorted(wrong_names)
        candidates.append(
            BackfillCandidate(
                kind="entity",
                link_key=link_key,
                payload={
                    "entity_type": "person",
                    "display_name": person_name,
                    "normalized_name": _normalize(person_name),
                    "aliases": [
                        alias
                        for alias in _person_aliases(content, person_name)
                        if _normalize(alias) not in wrong_names
                    ],
                    "relationship": _dating_relationship(content),
                    "summary": _person_summary(content, person_name),
                    "source_conversation_id": memory.get("source_conversation_id"),
                    "source_message_id": memory.get("source_message_id"),
                    "source_memory_id": memory.get("id"),
                    "importance": max(3, int(memory.get("importance") or 3)),
                    "metadata": correction_metadata,
                },
            )
        )
        if _looks_like_dating_plan(content):
            candidates.append(
                BackfillCandidate(
                    kind="plan",
                    link_key=link_key,
                    payload={
                        "plan_type": "dating",
                        "title": f"Ask {person_name} out for dinner",
                        "description": content,
                        "desired_outcome": f"Successful date with {person_name}",
                        "source_conversation_id": memory.get(
                            "source_conversation_id"
                        ),
                        "source_message_id": memory.get("source_message_id"),
                        "source_memory_id": memory.get("id"),
                        "priority": max(3, int(memory.get("importance") or 3)),
                        "metadata": correction_metadata,
                    },
                )
            )

    rule = _extract_simple_rule(content, memory.get("memory_type"))
    if rule:
        rule["source_conversation_id"] = memory.get("source_conversation_id")
        rule["source_message_id"] = memory.get("source_message_id")
        rule["source_memory_id"] = memory.get("id")
        rule["metadata"] = source_metadata
        candidates.append(BackfillCandidate(kind="rule", payload=rule))

    return candidates


def _extract_us_state(content: str) -> str | None:
    lowered = content.casefold()
    if not re.search(r"\b(?:i am|i'm|i live|i'm living|living)\s+in\b", lowered):
        return None
    for state in sorted(US_STATES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(state)}\b", content, flags=re.IGNORECASE):
            return state
    return None


def _extract_dating_person_name(content: str) -> str | None:
    correction_match = re.search(
        r"\b(?:person|name)(?:[^.]{0,80})\bis\s+([A-Z][a-z]{2,})\b",
        content,
    )
    if correction_match and _valid_person_name(correction_match.group(1)):
        return correction_match.group(1)

    for pattern in (
        r"\b(?:ask|asked|asking|invite|invited|inviting)\s+([A-Z][a-z]{2,})\b",
        r"\b([A-Z][a-z]{2,})['’]s\s+(?:day off|off day)\b",
    ):
        match = re.search(pattern, content)
        if match and _valid_person_name(match.group(1)):
            return match.group(1)
    return None


def _extract_simple_rule(
    content: str, memory_type: Any
) -> dict[str, Any] | None:
    if memory_type != "preference":
        return None
    lowered = content.casefold()
    if not re.search(r"\b(?:do not|don't|avoid|stop|no more|limit)\b", lowered):
        return None

    rule_type = "personal"
    keywords: list[str] = []
    if any(term in lowered for term in ("uber", "lyft", "taxi")):
        rule_type = "transport"
        keywords = ["uber", "lyft", "taxi"]
    elif any(term in lowered for term in ("doordash", "uber eats", "delivery")):
        rule_type = "food_delivery"
        keywords = ["doordash", "uber eats", "delivery"]
    elif "coffee" in lowered:
        rule_type = "coffee"
        keywords = ["coffee"]
    elif any(term in lowered for term in ("spend", "spending", "budget")):
        rule_type = "finance"
        keywords = ["spending", "budget"]

    if rule_type == "personal":
        return None
    return {
        "rule_type": rule_type,
        "title": _rule_title(rule_type),
        "rule_text": content,
        "trigger_keywords": keywords,
        "priority": 3,
    }


def _looks_like_dating_plan(content: str) -> bool:
    lowered = content.casefold()
    return "date plan" in lowered or (
        any(term in lowered for term in ("date", "dinner", "restaurant"))
        and any(term in lowered for term in ("ask", "asked", "invite", "invited"))
    )


def _person_aliases(content: str, person_name: str) -> list[str]:
    aliases = []
    if re.search(r"\b(?:girl|person|coworker) (?:from|at) work\b", content, re.I):
        aliases.extend(["girl from work", "coworker"])
    for alias in ("Al", "AI"):
        if alias.casefold() != person_name.casefold() and re.search(
            rf"\b{alias}\b",
            content,
            flags=re.IGNORECASE,
        ):
            aliases.append(alias)
    return _dedupe(aliases)


def _dating_relationship(content: str) -> str | None:
    lowered = content.casefold()
    if "work" in lowered or "coworker" in lowered:
        return "coworker / dating interest"
    if _looks_like_dating_plan(content):
        return "dating interest"
    return None


def _person_summary(content: str, person_name: str) -> str:
    if _looks_like_dating_plan(content):
        return f"{person_name} is connected to the user's dating plan."
    return f"{person_name} is a person the user mentioned."


def _valid_person_name(name: str) -> bool:
    return name.casefold() not in AMBIGUOUS_PERSON_NAMES


def _rule_title(rule_type: str) -> str:
    return {
        "transport": "Transport spending rule",
        "food_delivery": "Food delivery rule",
        "coffee": "Coffee rule",
        "finance": "Spending rule",
    }.get(rule_type, "Personal rule")


def _source_metadata(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "backfilled_from": "long_term_memory",
        "backfill_version": BACKFILL_VERSION,
        "source_memory_id": memory.get("id"),
        "source_content": memory.get("content"),
    }


def _upserted_row(kind: str, row: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": row.get("id"),
        "source_memory_id": memory.get("id"),
        "title": row.get("display_name") or row.get("title"),
    }


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill obvious flat memories into structured memory tables."
    )
    parser.add_argument("--apply", action="store_true", help="Write backfilled rows.")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    await startup_http_client()
    try:
        report = await backfill_structured_memory(
            SupabaseMemoryService(),
            apply=args.apply,
            limit=args.limit,
        )
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    finally:
        await shutdown_http_client()


if __name__ == "__main__":
    asyncio.run(_main())
