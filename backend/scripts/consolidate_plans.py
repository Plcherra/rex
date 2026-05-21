from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.http_client import shutdown_http_client, startup_http_client
from app.services.memory_service import SupabaseMemoryService


CONSOLIDATION_VERSION = 1


@dataclass(frozen=True)
class PlanCluster:
    name: str
    keep: dict[str, Any]
    archive: list[dict[str, Any]]


@dataclass
class PlanConsolidationReport:
    dry_run: bool
    scanned: int = 0
    clusters: list[dict[str, Any]] = field(default_factory=list)
    milestones_created: list[dict[str, Any]] = field(default_factory=list)
    plans_updated: list[dict[str, Any]] = field(default_factory=list)
    archived: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "scanned": self.scanned,
            "clusters": self.clusters,
            "milestones_created": self.milestones_created,
            "plans_updated": self.plans_updated,
            "archived": self.archived,
            "errors": self.errors,
        }


async def consolidate_plans(
    memory_service: SupabaseMemoryService,
    *,
    apply: bool = False,
    limit: int = 200,
) -> PlanConsolidationReport:
    report = PlanConsolidationReport(dry_run=not apply)
    plans = await memory_service.list_plans(active=True, limit=limit)
    milestones = await memory_service.list_plan_milestones(active=True, limit=500)
    report.scanned = len(plans)

    archived_ids: set[str] = set()
    for cluster in build_plan_clusters(plans):
        archive = [
            plan
            for plan in cluster.archive
            if plan.get("id") not in archived_ids
            and plan.get("id") != cluster.keep.get("id")
        ]
        if not archive:
            continue

        report.clusters.append(_cluster_preview(cluster.name, cluster.keep, archive))
        if not apply:
            archived_ids.update(str(plan.get("id")) for plan in archive)
            continue

        for plan in archive:
            try:
                if _source_plan_should_be_milestone(plan):
                    milestone = await _create_consolidated_milestone(
                        memory_service,
                        milestones,
                        cluster.name,
                        cluster.keep,
                        plan,
                    )
                    if milestone:
                        milestones.append(milestone)
                        report.milestones_created.append(
                            {
                                "id": milestone.get("id"),
                                "plan_id": milestone.get("plan_id"),
                                "title": milestone.get("title"),
                                "source_plan_id": plan.get("id"),
                            }
                        )
                else:
                    updated_keep = await _merge_plan_detail_into_keep(
                        memory_service,
                        cluster.name,
                        cluster.keep,
                        plan,
                    )
                    if updated_keep:
                        cluster.keep.update(updated_keep)
                        report.plans_updated.append(
                            {
                                "id": cluster.keep.get("id"),
                                "title": cluster.keep.get("title"),
                                "merged_source_plan_id": plan.get("id"),
                                "merged_source_title": plan.get("title"),
                            }
                        )

                updated = await memory_service.update_plan(
                    str(plan["id"]),
                    active=False,
                    status="archived",
                    metadata=_archived_metadata(cluster.name, cluster.keep, plan),
                )
                report.archived.append(
                    {
                        "id": plan.get("id"),
                        "title": plan.get("title"),
                        "consolidated_into_plan_id": cluster.keep.get("id"),
                        "consolidated_into_title": cluster.keep.get("title"),
                    }
                )
                if updated:
                    archived_ids.add(str(plan.get("id")))
            except Exception as error:  # pragma: no cover - CLI safety net
                report.errors.append(
                    {
                        "cluster": cluster.name,
                        "plan_id": str(plan.get("id")),
                        "error": str(error),
                    }
                )

    return report


def build_plan_clusters(plans: list[dict[str, Any]]) -> list[PlanCluster]:
    active = [plan for plan in plans if _is_active(plan)]
    clusters: list[PlanCluster] = []
    clusters.extend(_dating_clusters(active))
    income_cluster = _single_topic_cluster(
        active,
        name="life_freedom_income",
        matcher=_is_income_or_relocation_plan,
        keep_selector=_select_income_root,
    )
    if income_cluster:
        clusters.append(income_cluster)
    app_cluster = _single_topic_cluster(
        active,
        name="app_development_roadmap",
        matcher=_is_app_development_plan,
        keep_selector=_select_app_root,
    )
    if app_cluster:
        clusters.append(app_cluster)
    return clusters


def _dating_clusters(plans: list[dict[str, Any]]) -> list[PlanCluster]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for plan in plans:
        if plan.get("plan_type") != "dating":
            continue
        key = _dating_key(plan)
        if not key:
            continue
        groups.setdefault(key, []).append(plan)

    clusters = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        keep = _select_best_plan(group, prefer_terms={"date", "next", "week"})
        clusters.append(
            PlanCluster(
                name=f"dating_{key}",
                keep=keep,
                archive=[plan for plan in group if plan.get("id") != keep.get("id")],
            )
        )
    return clusters


def _single_topic_cluster(
    plans: list[dict[str, Any]],
    *,
    name: str,
    matcher: Any,
    keep_selector: Any,
) -> PlanCluster | None:
    group = [plan for plan in plans if matcher(plan)]
    if len(group) < 2:
        return None
    keep = keep_selector(group)
    return PlanCluster(
        name=name,
        keep=keep,
        archive=[plan for plan in group if plan.get("id") != keep.get("id")],
    )


def _select_income_root(group: list[dict[str, Any]]) -> dict[str, Any]:
    for term in ("relocate", "europe", "location independent", "location-independent"):
        matches = [plan for plan in group if term in _plan_text(plan)]
        if matches:
            return _select_best_plan(matches)
    return _select_best_plan(group, prefer_terms={"income", "monthly", "5k"})


def _select_app_root(group: list[dict[str, Any]]) -> dict[str, Any]:
    for phrase in ("three month app development", "three-month app development"):
        matches = [plan for plan in group if phrase in _plan_text(plan)]
        if matches:
            return _select_best_plan(matches)
    return _select_best_plan(group, prefer_terms={"app", "development", "roadmap"})


def _select_best_plan(
    group: list[dict[str, Any]],
    *,
    prefer_terms: set[str] | None = None,
) -> dict[str, Any]:
    prefer_terms = prefer_terms or set()
    return max(
        group,
        key=lambda plan: (
            int(plan.get("priority") or 3),
            len(_tokens(plan) & prefer_terms),
            str(plan.get("updated_at") or plan.get("created_at") or ""),
        ),
    )


def _is_income_or_relocation_plan(plan: dict[str, Any]) -> bool:
    if plan.get("plan_type") not in {
        "career",
        "finance",
        "housing",
        "immigration",
        "personal",
    }:
        return False
    text = _plan_text(plan)
    if any(
        term in text
        for term in ("income", "5k", "5000", "3k", "3000", "saving", "savings")
    ):
        return True
    return any(
        term in text
        for term in (
            "abroad",
            "citizenship",
            "digital nomad",
            "estonia",
            "europe",
            "immigration",
            "italian",
            "italy",
            "location independent",
            "relocate",
            "relocating",
            "relocation",
            "residency",
            "visa",
        )
    )


def _is_app_development_plan(plan: dict[str, Any]) -> bool:
    if plan.get("plan_type") not in {"career", "creative", "other", "personal"}:
        return False
    text = _plan_text(plan)
    if "income" in text or "5k" in text or "3k" in text:
        return False
    app_terms = {
        "app",
        "apps",
        "clarity",
        "development",
        "echodesk",
        "flowforce",
        "launch",
        "rex",
    }
    return len(_tokens(plan) & app_terms) >= 2


def _dating_key(plan: dict[str, Any]) -> str | None:
    text = _plan_text(plan)
    for token in _tokens(plan):
        if token in {"al", "ai"}:
            continue
        if re.search(rf"\b{re.escape(token)}\b", text) and token in _person_tokens(plan):
            return f"person_{token}"
    primary_entity_id = plan.get("primary_entity_id")
    if primary_entity_id:
        return f"entity_{primary_entity_id}"
    return None


def _person_tokens(plan: dict[str, Any]) -> set[str]:
    raw_text = " ".join(
        str(plan.get(field) or "")
        for field in ("title", "description", "desired_outcome")
    )
    names = {
        match.group(0).casefold()
        for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", raw_text)
    }
    return names - {
        "ask",
        "clear",
        "date",
        "dinner",
        "meetup",
        "monday",
        "next",
        "outing",
        "positive",
        "pursuing",
        "successful",
        "thursday",
    }


def _create_milestone_payload(
    cluster_name: str,
    keep: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        "plan_id": keep["id"],
        "title": str(source.get("title") or "Consolidated plan detail"),
        "description": _source_plan_detail(source),
        "milestone_type": "goal",
        "source_conversation_id": source.get("source_conversation_id"),
        "source_message_id": source.get("source_message_id"),
        "source_memory_id": source.get("source_memory_id"),
        "priority": int(source.get("priority") or 3),
        "status": "open",
        "active": True,
        "metadata": {
            "consolidation_version": CONSOLIDATION_VERSION,
            "consolidation_cluster": cluster_name,
            "consolidated_from_plan_id": source.get("id"),
            "source_plan_type": source.get("plan_type"),
        },
    }


async def _create_consolidated_milestone(
    memory_service: SupabaseMemoryService,
    existing_milestones: list[dict[str, Any]],
    cluster_name: str,
    keep: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any] | None:
    payload = _create_milestone_payload(cluster_name, keep, source)
    if _milestone_exists(existing_milestones, payload):
        return None
    return await memory_service.create_plan_milestone(payload)


async def _merge_plan_detail_into_keep(
    memory_service: SupabaseMemoryService,
    cluster_name: str,
    keep: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any] | None:
    detail = _source_plan_detail_with_title(source)
    if not detail:
        return None
    current_description = _clean_text(keep.get("description")) or ""
    if _normalize(detail) in _normalize(current_description):
        return None
    merged_description = (
        f"{current_description} Consolidated context: {detail}"
        if current_description
        else detail
    )
    metadata = {
        **(keep.get("metadata") or {}),
        "consolidation_version": CONSOLIDATION_VERSION,
        "consolidation_cluster": cluster_name,
        "merged_plan_details": [
            *(
                (keep.get("metadata") or {}).get("merged_plan_details")
                if isinstance((keep.get("metadata") or {}).get("merged_plan_details"), list)
                else []
            ),
            {
                "source_plan_id": source.get("id"),
                "source_title": source.get("title"),
            },
        ],
    }
    return await memory_service.update_plan(
        str(keep["id"]),
        description=merged_description,
        metadata=metadata,
    )


def _source_plan_should_be_milestone(plan: dict[str, Any]) -> bool:
    text = _plan_text(plan)
    if "first million" in text:
        return False
    if plan.get("plan_type") == "dating":
        return False
    if _looks_like_strategy_variant(text):
        return False
    if re.search(r"(?:[$€]\s*)?\d+(?:\.\d+)?\s*k\b|[$€]\s*\d{3,}", text):
        return True
    tokens = set(text.split())
    if tokens & {
        "approval",
        "approved",
        "complete",
        "completed",
        "finish",
        "finished",
        "launch",
        "launched",
        "secure",
        "secured",
        "ship",
        "shipped",
        "submit",
        "submitted",
    }:
        return True
    return False


def _looks_like_strategy_variant(text: str) -> bool:
    if text.startswith(("europe relocation via", "european relocation via")):
        return True
    return bool(
        {
            "plan",
            "strategy",
            "roadmap",
            "sequence",
            "route",
            "routes",
            "considering",
            "exploring",
        }
        & set(text.split())
    )


def _milestone_exists(
    milestones: list[dict[str, Any]],
    payload: dict[str, Any],
) -> bool:
    source_plan_id = payload["metadata"]["consolidated_from_plan_id"]
    normalized_title = _normalize(payload.get("title"))
    for milestone in milestones:
        if milestone.get("plan_id") != payload.get("plan_id"):
            continue
        metadata = milestone.get("metadata") or {}
        if metadata.get("consolidated_from_plan_id") == source_plan_id:
            return True
        if _normalize(milestone.get("title")) == normalized_title:
            return True
    return False


def _archived_metadata(
    cluster_name: str,
    keep: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        **(source.get("metadata") or {}),
        "cleanup_reason": "plan_consolidation",
        "consolidation_version": CONSOLIDATION_VERSION,
        "consolidation_cluster": cluster_name,
        "consolidated_into_plan_id": keep.get("id"),
        "consolidated_into_title": keep.get("title"),
    }


def _cluster_preview(
    name: str,
    keep: dict[str, Any],
    archive: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "keep": _plan_preview(keep),
        "archive": [_plan_preview(plan) for plan in archive],
        "milestones_to_create": [
            {
                "plan_id": keep.get("id"),
                "title": plan.get("title"),
                "source_plan_id": plan.get("id"),
            }
            for plan in archive
            if _source_plan_should_be_milestone(plan)
        ],
        "plan_details_to_merge": [
            {
                "plan_id": keep.get("id"),
                "title": plan.get("title"),
                "source_plan_id": plan.get("id"),
            }
            for plan in archive
            if not _source_plan_should_be_milestone(plan)
        ],
    }


def _plan_preview(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": plan.get("id"),
        "title": plan.get("title"),
        "plan_type": plan.get("plan_type"),
        "priority": plan.get("priority"),
    }


def _source_plan_detail(plan: dict[str, Any]) -> str | None:
    parts = [
        _clean_text(plan.get("description")),
        _clean_text(plan.get("desired_outcome")),
    ]
    detail = " ".join(part for part in parts if part)
    return detail or None


def _source_plan_detail_with_title(plan: dict[str, Any]) -> str | None:
    parts = [
        _clean_text(plan.get("title")),
        _clean_text(plan.get("description")),
        _clean_text(plan.get("desired_outcome")),
    ]
    detail = " ".join(part for part in parts if part)
    return detail or None


def _is_active(plan: dict[str, Any]) -> bool:
    return plan.get("active") is not False and plan.get("status", "active") == "active"


def _tokens(plan: dict[str, Any]) -> set[str]:
    return set(_plan_text(plan).split())


def _plan_text(plan: dict[str, Any]) -> str:
    return _normalize(
        " ".join(
            str(plan.get(field) or "")
            for field in ("title", "description", "desired_outcome")
        )
    )


def _clean_text(value: Any) -> str | None:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    return cleaned or None


def _normalize(value: Any) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Consolidate duplicate top-level structured plans into milestones."
    )
    parser.add_argument("--apply", action="store_true", help="Archive duplicate plans.")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    await startup_http_client()
    try:
        report = await consolidate_plans(
            SupabaseMemoryService(),
            apply=args.apply,
            limit=args.limit,
        )
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    finally:
        await shutdown_http_client()


if __name__ == "__main__":
    asyncio.run(_main())
