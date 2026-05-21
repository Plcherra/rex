from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class VerificationTableSpec:
    table: str
    list_method: str
    text_fields: tuple[str, ...]


VERIFICATION_TABLES = (
    VerificationTableSpec(
        table="long_term_memory",
        list_method="list_long_term_memory",
        text_fields=("content",),
    ),
    VerificationTableSpec(
        table="entities",
        list_method="list_entities",
        text_fields=("display_name", "normalized_name", "aliases", "relationship", "summary"),
    ),
    VerificationTableSpec(
        table="entity_events",
        list_method="list_entity_events",
        text_fields=("title", "content"),
    ),
    VerificationTableSpec(
        table="personal_rules",
        list_method="list_personal_rules",
        text_fields=("title", "rule_text", "trigger_keywords"),
    ),
    VerificationTableSpec(
        table="plans",
        list_method="list_plans",
        text_fields=("title", "description", "desired_outcome"),
    ),
    VerificationTableSpec(
        table="plan_milestones",
        list_method="list_plan_milestones",
        text_fields=("title", "description"),
    ),
    VerificationTableSpec(
        table="commitments",
        list_method="list_commitments",
        text_fields=("title", "commitment_text"),
    ),
)


class MemoryVerificationRepository(Protocol):
    async def list_long_term_memory(
        self,
        limit: int = 50,
        memory_type: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        pass


class MemoryVerificationService:
    def __init__(self, memory_service: MemoryVerificationRepository, *, scan_limit: int = 250):
        self.memory_service = memory_service
        self.scan_limit = scan_limit

    async def verify_applied_record(
        self,
        *,
        table: str | None,
        record_id: str | None,
    ) -> dict[str, Any]:
        if not table or not record_id:
            return {
                "passed": False,
                "checked_tables": [table] if table else [],
                "remaining_conflicts": [],
                "applied_record": {
                    "table": table,
                    "id": record_id,
                },
                "message": "Candidate apply did not return a durable record id.",
            }

        spec = next((item for item in VERIFICATION_TABLES if item.table == table), None)
        if spec is None:
            return {
                "passed": False,
                "checked_tables": [table],
                "remaining_conflicts": [],
                "applied_record": {
                    "table": table,
                    "id": record_id,
                },
                "message": "Candidate apply returned an unsupported table for verification.",
            }

        records = await self._safe_list(spec)
        found = next(
            (record for record in records if str(record.get("id") or "") == str(record_id)),
            None,
        )
        passed = found is not None
        return {
            "passed": passed,
            "checked_tables": [table],
            "remaining_conflicts": [],
            "applied_record": {
                "table": table,
                "id": record_id,
                "title": _record_title(found or {}),
            },
            "message": (
                "Candidate verified. Durable active record is readable."
                if passed
                else "Candidate apply returned a record id, but the active record was not readable."
            ),
        }

    async def verify_correction(
        self,
        *,
        stale_terms: list[str],
        applied_record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_terms = [_normalize_text(term) for term in stale_terms if _normalize_text(term)]
        checked_tables: list[str] = []
        remaining: list[dict[str, Any]] = []
        if not clean_terms:
            return {
                "passed": True,
                "checked_tables": [],
                "remaining_conflicts": [],
                "applied_record": applied_record,
                "message": "No stale terms were provided for verification.",
            }

        for spec in VERIFICATION_TABLES:
            checked_tables.append(spec.table)
            records = await self._safe_list(spec)
            for record in records:
                matches = _matching_terms(record, spec, clean_terms)
                if not matches:
                    continue
                remaining.append(
                    {
                        "table": spec.table,
                        "id": record.get("id"),
                        "title": _record_title(record),
                        "matched_terms": matches,
                    }
                )

        return {
            "passed": not remaining,
            "checked_tables": checked_tables,
            "remaining_conflicts": remaining,
            "applied_record": applied_record,
            "message": (
                "Correction verified. No active records contain the stale terms."
                if not remaining
                else "Correction verification failed. Active records still contain stale terms."
            ),
        }

    async def _safe_list(self, spec: VerificationTableSpec) -> list[dict[str, Any]]:
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


def _matching_terms(
    record: dict[str, Any],
    spec: VerificationTableSpec,
    terms: list[str],
) -> list[str]:
    haystack = " ".join(_field_text(record.get(field)) for field in spec.text_fields)
    normalized = _normalize_text(haystack)
    return [term for term in terms if term in normalized]


def _field_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_field_text(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _record_title(record: dict[str, Any]) -> str | None:
    for key in ("title", "display_name", "content", "rule_text", "commitment_text"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return None


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())
