from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from typing import Any

from app.services.http_client import shutdown_http_client, startup_http_client
from app.services.memory_correction_service import MemoryCorrectionService
from app.services.memory_service import SupabaseMemoryService


async def run_correction(
    correction: str,
    *,
    apply: bool = False,
    force: bool = False,
    limit: int = 250,
) -> dict:
    memory_service = SupabaseMemoryService()
    service = MemoryCorrectionService(memory_service, scan_limit=limit)
    intent = service.detect_correction_intent(correction)
    if not apply:
        return {
            "dry_run": True,
            "intent": {
                "intent_type": intent.intent_type.value,
                "old_value": intent.old_value,
                "new_value": intent.new_value,
                "target_hint": intent.target_hint,
                "confidence": intent.confidence,
                "requires_confirmation": intent.requires_confirmation,
            },
        }
    report = await service.apply_correction(correction, force=force)
    return report.as_dict()


async def run_audit(
    memory_service: Any,
    *,
    limit: int = 500,
    apply: bool = False,
) -> dict:
    plans, rules, entities, milestones, commitments = await asyncio.gather(
        _safe_list(memory_service, "list_plans", active=True, limit=limit),
        _safe_list(memory_service, "list_personal_rules", active=True, limit=limit),
        _safe_list(memory_service, "list_entities", active=True, limit=limit),
        _safe_list(memory_service, "list_plan_milestones", active=True, limit=limit),
        _safe_list(memory_service, "list_commitments", active=True, limit=limit),
    )
    duplicate_clusters = [
        *_duplicate_clusters(plans, "plan", ("title", "description", "desired_outcome")),
        *_duplicate_clusters(rules, "rule", ("title", "rule_text")),
        *_duplicate_clusters(entities, "entity", ("display_name", "normalized_name")),
    ]

    return {
        "dry_run": not apply,
        "applied": False,
        "message": (
            "Audit only. Use specific correction text with --apply for now."
            if apply
            else "Dry-run audit only. No records were changed."
        ),
        "records_scanned": {
            "plans": len(plans),
            "rules": len(rules),
            "entities": len(entities),
            "milestones": len(milestones),
            "commitments": len(commitments),
        },
        "duplicate_clusters": duplicate_clusters,
        "updates": [],
        "archives": [],
        "milestones_created": [],
        "tasks_created": [],
        "errors": [],
    }


async def _safe_list(memory_service: Any, method_name: str, **kwargs: Any) -> list[dict]:
    method = getattr(memory_service, method_name, None)
    if method is None:
        return []
    try:
        return await method(**kwargs)
    except Exception as error:
        return [{"_error": str(error), "_method": method_name}]


def _duplicate_clusters(
    records: list[dict],
    record_type: str,
    fields: tuple[str, ...],
) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("_error"):
            continue
        key = _duplicate_key(record, fields)
        if key:
            groups[key].append(record)

    clusters = []
    for group in groups.values():
        if len(group) < 2:
            continue
        clusters.append(
            {
                "record_type": record_type,
                "record_ids": [
                    str(record.get("id")) for record in group if record.get("id")
                ],
                "titles": [
                    str(
                        record.get("title")
                        or record.get("display_name")
                        or record.get("normalized_name")
                        or ""
                    )
                    for record in group
                ],
            }
        )
    return clusters


def _duplicate_key(record: dict, fields: tuple[str, ...]) -> str:
    text = " ".join(str(record.get(field) or "") for field in fields).casefold()
    tokens = [
        token
        for token in re.findall(r"[a-z0-9$]+", text)
        if len(token) > 2
        and token not in {"active", "and", "for", "from", "plan", "the", "this", "with"}
    ]
    return " ".join(tokens[:8])


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply reusable memory discipline correction workflows."
    )
    parser.add_argument(
        "correction",
        nargs="?",
        help="Correction text to classify or apply. Omit for dry-run audit.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply the correction.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply even when the correction is high-impact or ambiguous.",
    )
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()

    await startup_http_client()
    try:
        if args.correction:
            report = await run_correction(
                args.correction,
                apply=args.apply,
                force=args.force,
                limit=args.limit,
            )
        else:
            report = await run_audit(
                SupabaseMemoryService(),
                apply=args.apply,
                limit=args.limit,
            )
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        await shutdown_http_client()


if __name__ == "__main__":
    asyncio.run(main())
