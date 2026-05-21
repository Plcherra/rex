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
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


class MemoryCandidateServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class MemoryCandidateService:
    def __init__(self, memory_service: SupabaseMemoryService) -> None:
        self.memory_service = memory_service

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
            "phase": "1a",
            "durable_apply_enabled": False,
        }
        updates = {
            "status": "approved",
            "approved_by": _clean_optional(request.approved_by) or "user",
            "approved_at": _now_iso(),
            "reason": _clean_optional(request.reason) or row.get("reason"),
            "decision": decision,
        }
        updated = await self._update_candidate(candidate_id, updates)
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
