from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.memory_candidate import (
    MemoryCandidateApproveRequest,
    MemoryCandidateBulkDecisionRequest,
    MemoryCandidateCreateRequest,
    MemoryCandidateRejectRequest,
    MemoryCandidateUpdateRequest,
)
from app.models.memory_discipline import MemoryCandidateKind, MemoryDisciplineCandidate
from app.models.memory_discipline import MemoryDisciplineAction
from app.services.memory_correction_service import MemoryCorrectionService
from app.services.memory_discipline_service import MemoryDisciplineService
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService
from app.services.memory_verification_service import MemoryVerificationService


class MemoryCandidateServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class MemoryCandidateService:
    def __init__(
        self,
        memory_service: SupabaseMemoryService,
        memory_discipline_service: MemoryDisciplineService | None = None,
        memory_correction_service: MemoryCorrectionService | None = None,
        memory_verification_service: MemoryVerificationService | None = None,
    ) -> None:
        self.memory_service = memory_service
        self.memory_discipline_service = (
            memory_discipline_service or MemoryDisciplineService(memory_service)
        )
        self.memory_correction_service = (
            memory_correction_service or MemoryCorrectionService(memory_service)
        )
        self.memory_verification_service = (
            memory_verification_service or MemoryVerificationService(memory_service)
        )

    async def create_candidate(
        self, request: MemoryCandidateCreateRequest
    ) -> dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        payload["payload"] = _clean_payload(payload.get("payload"))
        payload["reason"] = _clean_optional(payload.get("reason"))
        try:
            row = await self.memory_service.create_memory_candidate(payload)
        except MemoryServiceError as error:
            raise MemoryCandidateServiceError(
                error.detail,
                error.status_code,
            ) from error
        return _with_preview(row)

    async def list_candidates(
        self,
        *,
        candidate_type: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        source_conversation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            rows = await self.memory_service.list_memory_candidates(
                candidate_type=candidate_type,
                status=status,
                risk_level=risk_level,
                source_conversation_id=source_conversation_id,
                limit=limit,
            )
        except MemoryServiceError as error:
            raise MemoryCandidateServiceError(
                error.detail,
                error.status_code,
            ) from error
        return [_with_preview(row) for row in rows]

    async def update_candidate(
        self,
        candidate_id: str,
        request: MemoryCandidateUpdateRequest,
    ) -> dict[str, Any]:
        updates = request.model_dump(exclude_none=True)
        if "payload" in updates:
            updates["payload"] = _clean_payload(updates["payload"])
        if "reason" in updates:
            updates["reason"] = _clean_optional(updates["reason"])
        if not updates:
            raise MemoryCandidateServiceError(
                "At least one memory candidate field must be provided.",
                400,
            )

        row = await self._update_candidate(candidate_id, updates)
        return _with_preview(row)

    async def approve_candidate(
        self,
        candidate_id: str,
        request: MemoryCandidateApproveRequest,
    ) -> dict[str, Any]:
        row = await self._get_pending_candidate(candidate_id)
        decision = {
            **(row.get("decision") or {}),
            **(request.decision or {}),
            "phase": "1b",
            "durable_apply_enabled": True,
        }
        approved_at = _now_iso()
        try:
            apply_result = await self._apply_candidate(row)
        except Exception as error:
            failed = await self._update_candidate(
                candidate_id,
                {
                    "status": "failed",
                    "approved_by": _clean_optional(request.approved_by) or "user",
                    "approved_at": approved_at,
                    "reason": _clean_optional(request.reason) or row.get("reason"),
                    "decision": {
                        **decision,
                        "error": str(error),
                    },
                    "verification": {
                        "passed": False,
                        "message": "Candidate approval failed before durable write completed.",
                    },
                },
            )
            return _with_preview(failed)

        if not apply_result.get("applied"):
            failed = await self._update_candidate(
                candidate_id,
                {
                    "status": "failed",
                    "approved_by": _clean_optional(request.approved_by) or "user",
                    "approved_at": approved_at,
                    "reason": _clean_optional(request.reason) or row.get("reason"),
                    "decision": {
                        **decision,
                        "apply_result": apply_result,
                    },
                    "verification": {
                        "passed": False,
                        "message": apply_result.get("reason")
                        or "Candidate could not be applied.",
                    },
                },
            )
            return _with_preview(failed)

        verification = await self._verification_for_applied(
            candidate=row,
            apply_result=apply_result,
        )
        record = apply_result.get("record") or {}
        updated = await self._update_candidate(
            candidate_id,
            {
                "status": "applied" if verification.get("passed") else "failed",
                "approved_by": _clean_optional(request.approved_by) or "user",
                "approved_at": approved_at,
                "applied_at": _now_iso() if verification.get("passed") else None,
                "reason": _clean_optional(request.reason) or row.get("reason"),
                "decision": {
                    **decision,
                    "apply_result": {
                        "action": apply_result.get("action"),
                        "applied": True,
                    },
                },
                "applied_record_table": apply_result.get("table"),
                "applied_record_id": record.get("id"),
                "verification": verification,
            },
        )
        return _with_preview(updated)

    async def reject_candidate(
        self,
        candidate_id: str,
        request: MemoryCandidateRejectRequest,
    ) -> dict[str, Any]:
        await self._get_pending_candidate(candidate_id)
        decision = {
            **(request.decision or {}),
            "phase": "1a",
            "rejected": True,
        }
        updates = {
            "status": "rejected",
            "rejected_at": _now_iso(),
            "reason": _clean_optional(request.reason),
            "decision": decision,
        }
        updated = await self._update_candidate(candidate_id, updates)
        return _with_preview(updated)

    async def bulk_approve_candidates(
        self,
        request: MemoryCandidateBulkDecisionRequest,
    ) -> dict[str, list[dict[str, Any]]]:
        candidates = await self._bulk_pending_candidates(request)
        approved: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for candidate in candidates:
            if candidate.get("risk_level") == "high" and not request.include_high_risk:
                skipped.append(_with_preview(candidate))
                continue
            approved.append(
                await self.approve_candidate(
                    candidate["id"],
                    MemoryCandidateApproveRequest(
                        approved_by=request.decided_by,
                        reason=request.reason,
                        decision={"bulk": True},
                    ),
                )
            )
        return {"approved": approved, "rejected": [], "skipped": skipped}

    async def bulk_reject_candidates(
        self,
        request: MemoryCandidateBulkDecisionRequest,
    ) -> dict[str, list[dict[str, Any]]]:
        candidates = await self._bulk_pending_candidates(request)
        rejected = [
            await self.reject_candidate(
                candidate["id"],
                MemoryCandidateRejectRequest(
                    reason=request.reason,
                    decision={"bulk": True, "decided_by": request.decided_by},
                ),
            )
            for candidate in candidates
        ]
        return {"approved": [], "rejected": rejected, "skipped": []}

    async def _bulk_pending_candidates(
        self,
        request: MemoryCandidateBulkDecisionRequest,
    ) -> list[dict[str, Any]]:
        if request.candidate_ids:
            candidates = [
                await self._get_pending_candidate(candidate_id)
                for candidate_id in request.candidate_ids
            ]
            return candidates
        return await self.list_candidates(
            status="pending",
            source_conversation_id=request.source_conversation_id,
            limit=100,
        )

    async def _get_pending_candidate(self, candidate_id: str) -> dict[str, Any]:
        try:
            row = await self.memory_service.get_memory_candidate(candidate_id)
        except MemoryServiceError as error:
            raise MemoryCandidateServiceError(
                error.detail,
                error.status_code,
            ) from error
        if row is None:
            raise MemoryCandidateServiceError("Pending memory candidate not found.", 404)
        if row.get("status") != "pending":
            raise MemoryCandidateServiceError("Pending memory candidate not found.", 404)
        return _with_preview(row)

    async def _update_candidate(
        self, candidate_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            row = await self.memory_service.update_memory_candidate(
                candidate_id,
                **updates,
            )
        except MemoryServiceError as error:
            raise MemoryCandidateServiceError(
                error.detail,
                error.status_code,
            ) from error
        if row is None:
            raise MemoryCandidateServiceError("Memory candidate not found.", 404)
        return row

    async def _apply_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        candidate_type = str(candidate.get("candidate_type") or "")
        payload = dict(candidate.get("payload") or {})
        discipline_hint = payload.pop("memory_discipline", None)
        if isinstance(discipline_hint, dict):
            payload["metadata"] = {
                **(payload.get("metadata") or {}),
                "memory_discipline": discipline_hint,
            }
        source_conversation_id = candidate.get("source_conversation_id")
        source_message_id = candidate.get("source_message_id")

        if candidate_type == "long_term_memory":
            memory_type = str(payload.get("memory_type") or "").strip()
            content = _clean_optional(payload.get("content"))
            if not memory_type or not content:
                return {
                    "applied": False,
                    "reason": "Long-term memory candidate is missing type or content.",
                }
            record = await self.memory_service.save_long_term_memory(
                memory_type=memory_type,
                content=content,
                source_conversation_id=source_conversation_id,
                source_message_id=source_message_id,
                importance=int(payload.get("importance") or 3),
                confidence=float(payload.get("confidence") or 0.75),
                metadata=payload.get("metadata") or {},
            )
            return {
                "action": "create_long_term_memory",
                "applied": True,
                "table": "long_term_memory",
                "record": record,
            }

        if candidate_type == "entity_event":
            record = await self.memory_service.create_entity_event(payload)
            return {
                "action": "create_entity_event",
                "applied": True,
                "table": "entity_events",
                "record": record,
            }

        if candidate_type == "correction":
            text = _clean_optional(payload.get("text") or payload.get("content"))
            if not text:
                return {
                    "applied": False,
                    "reason": "Correction candidate is missing correction text.",
                }
            report = await self.memory_correction_service.apply_correction(
                text,
                source_conversation_id=source_conversation_id,
                source_message_id=source_message_id,
                force=True,
            )
            report_payload = report.as_dict()
            return {
                "action": "apply_correction",
                "applied": bool(report.applied),
                "table": "memory_corrections",
                "record": _correction_record(report_payload),
                "correction_report": report_payload,
                "stale_terms": _correction_stale_terms(report_payload),
                "reason": (
                    None
                    if report.applied
                    else "Correction did not affect any active records."
                ),
            }

        kind = _candidate_kind(candidate_type)
        if kind is None:
            return {
                "applied": False,
                "reason": f"Candidate type {candidate_type} is not applyable in Phase 1b.",
            }
        if candidate_type == "plan" and not _clean_optional(payload.get("description")):
            return {
                "applied": False,
                "reason": (
                    "Top-level plan candidates need a clear description before "
                    "they can be approved."
                ),
            }

        discipline_candidate = MemoryDisciplineCandidate(
            kind=kind,
            payload=payload,
            source_conversation_id=source_conversation_id,
            source_message_id=source_message_id,
            source_memory_id=payload.get("source_memory_id"),
        )
        decision = await self.memory_discipline_service.decide(discipline_candidate)
        if decision.action == MemoryDisciplineAction.ASK_CONFIRMATION:
            create_action = _create_action_for_kind(kind)
            if create_action is None:
                return {
                    "applied": False,
                    "reason": decision.reason,
                    "requires_confirmation": True,
                }
            decision = decision.model_copy(
                update={
                    "action": create_action,
                    "requires_confirmation": False,
                    "reason": (
                        "User explicitly approved the pending memory candidate."
                    ),
                }
            )
        applied = await self.memory_discipline_service.apply_decision(decision)
        if not applied.get("applied"):
            return {
                **applied,
                "table": _table_for_apply_action(applied.get("action"))
                or _table_for_candidate_type(candidate_type),
            }
        return {
            **applied,
            "table": _table_for_apply_action(applied.get("action"))
            or _table_for_candidate_type(candidate_type),
        }

    async def _verification_for_applied(
        self,
        *,
        candidate: dict[str, Any],
        apply_result: dict[str, Any],
    ) -> dict[str, Any]:
        if candidate.get("candidate_type") == "correction":
            report = apply_result.get("correction_report") or {}
            verification = await self.memory_verification_service.verify_correction(
                stale_terms=apply_result.get("stale_terms") or [],
                applied_record={
                    "table": apply_result.get("table"),
                    "id": (apply_result.get("record") or {}).get("id"),
                },
            )
            verification["correction_report"] = report
            return verification

        record = apply_result.get("record") or {}
        table = apply_result.get("table")
        return await self.memory_verification_service.verify_applied_record(
            table=table,
            record_id=record.get("id"),
        )


def _clean_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise MemoryCandidateServiceError(
            "Memory candidate payload must be an object.",
            400,
        )
    return payload


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _with_preview(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "preview": _preview(row)}


def _preview(row: dict[str, Any]) -> str:
    payload = row.get("payload") or {}
    candidate_type = str(row.get("candidate_type") or "memory")
    title = _first_text(
        payload,
        "title",
        "display_name",
        "content",
        "rule_text",
        "commitment_text",
        "new_value",
    )
    action = _first_text(payload, "action", "operation")
    if action and title:
        return f"{candidate_type}: {action} {title}"
    if title:
        return f"{candidate_type}: {title}"
    return f"{candidate_type}: pending memory change"


def _first_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = _clean_optional(value)
        if text:
            return text
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_kind(candidate_type: str) -> MemoryCandidateKind | None:
    return {
        "entity": MemoryCandidateKind.ENTITY,
        "entity_event": MemoryCandidateKind.ENTITY_EVENT,
        "personal_rule": MemoryCandidateKind.PERSONAL_RULE,
        "plan": MemoryCandidateKind.PLAN,
        "plan_milestone": MemoryCandidateKind.PLAN_MILESTONE,
        "commitment": MemoryCandidateKind.COMMITMENT,
    }.get(candidate_type)


def _create_action_for_kind(kind: MemoryCandidateKind) -> MemoryDisciplineAction | None:
    return {
        MemoryCandidateKind.ENTITY: MemoryDisciplineAction.CREATE_ENTITY,
        MemoryCandidateKind.ENTITY_EVENT: MemoryDisciplineAction.CREATE_ENTITY_EVENT,
        MemoryCandidateKind.PERSONAL_RULE: MemoryDisciplineAction.CREATE_RULE,
        MemoryCandidateKind.PLAN: MemoryDisciplineAction.CREATE_PLAN,
        MemoryCandidateKind.PLAN_MILESTONE: MemoryDisciplineAction.CREATE_MILESTONE,
        MemoryCandidateKind.COMMITMENT: MemoryDisciplineAction.CREATE_COMMITMENT,
    }.get(kind)


def _table_for_candidate_type(candidate_type: str) -> str | None:
    return {
        "long_term_memory": "long_term_memory",
        "entity": "entities",
        "entity_event": "entity_events",
        "personal_rule": "personal_rules",
        "plan": "plans",
        "plan_milestone": "plan_milestones",
        "commitment": "commitments",
        "correction": "memory_corrections",
    }.get(candidate_type)


def _table_for_apply_action(action: object) -> str | None:
    return {
        "create_entity": "entities",
        "update_entity": "entities",
        "create_entity_event": "entity_events",
        "create_plan": "plans",
        "update_plan": "plans",
        "create_milestone": "plan_milestones",
        "update_milestone": "plan_milestones",
        "create_commitment": "commitments",
        "update_commitment": "commitments",
        "create_rule": "personal_rules",
        "update_rule": "personal_rules",
    }.get(str(action or ""))


def _correction_record(report: dict[str, Any]) -> dict[str, Any]:
    corrections = report.get("corrections") or []
    if corrections:
        first = corrections[0]
        return {
            "id": first.get("id"),
            "correction_ids": [
                correction.get("id")
                for correction in corrections
                if correction.get("id") is not None
            ],
        }
    affected = report.get("affected_records") or []
    if affected:
        first = affected[0]
        return {
            "id": f"{first.get('table')}:{first.get('id')}",
            "affected_records": affected,
        }
    return {"id": None}


def _correction_stale_terms(report: dict[str, Any]) -> list[str]:
    stale_terms = report.get("verification_stale_terms") or []
    if stale_terms:
        return [
            term
            for term in (_clean_optional(stale_term) for stale_term in stale_terms)
            if term
        ]
    intent = report.get("intent") or {}
    old_value = _clean_optional(intent.get("old_value"))
    return [old_value] if old_value else []
