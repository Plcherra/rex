import pytest

from app.models.memory_candidate import (
    MemoryCandidateApproveRequest,
    MemoryCandidateBulkDecisionRequest,
    MemoryCandidateCreateRequest,
    MemoryCandidateRejectRequest,
    MemoryCandidateUpdateRequest,
)
from app.services.memory_candidate_service import (
    MemoryCandidateService,
    MemoryCandidateServiceError,
)
from app.services.memory_service import MemoryServiceError


class FakeMemoryCandidateRepository:
    def __init__(self, error=None):
        self.error = error
        self.candidates = []
        self.durable_writes = []

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def create_memory_candidate(self, payload):
        self._raise_if_configured()
        row = {
            "id": f"candidate-{len(self.candidates) + 1}",
            "status": "pending",
            "decision": None,
            "reason": None,
            "approved_by": None,
            "approved_at": None,
            "applied_at": None,
            "rejected_at": None,
            "applied_record_table": None,
            "applied_record_id": None,
            "verification": None,
            "created_at": "2026-05-21T00:00:00+00:00",
            "updated_at": "2026-05-21T00:00:00+00:00",
            **payload,
        }
        self.candidates.append(row)
        return row

    async def list_memory_candidates(
        self,
        limit=50,
        candidate_type=None,
        status=None,
        risk_level=None,
        source_conversation_id=None,
    ):
        self._raise_if_configured()
        rows = self.candidates
        if candidate_type is not None:
            rows = [row for row in rows if row.get("candidate_type") == candidate_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if risk_level is not None:
            rows = [row for row in rows if row.get("risk_level") == risk_level]
        if source_conversation_id is not None:
            rows = [
                row
                for row in rows
                if row.get("source_conversation_id") == source_conversation_id
            ]
        return rows[:limit]

    async def get_memory_candidate(self, candidate_id):
        self._raise_if_configured()
        return next(
            (row for row in self.candidates if row["id"] == candidate_id),
            None,
        )

    async def update_memory_candidate(self, candidate_id, **updates):
        self._raise_if_configured()
        for row in self.candidates:
            if row["id"] == candidate_id:
                row.update({key: value for key, value in updates.items() if value is not None})
                return row
        return None

    async def create_plan(self, payload):
        self.durable_writes.append(("plans", payload))
        return {"id": "plan-1", **payload}


@pytest.mark.asyncio
async def test_create_list_update_and_preview_candidate():
    repo = FakeMemoryCandidateRepository()
    service = MemoryCandidateService(repo)

    created = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="plan",
            payload={"title": "Move out of the country next year"},
            risk_level="high",
            source_conversation_id="conversation-1",
        )
    )

    assert created["preview"] == "plan: Move out of the country next year"
    assert created["status"] == "pending"

    listed = await service.list_candidates(
        status="pending",
        risk_level="high",
        source_conversation_id="conversation-1",
    )
    assert [candidate["id"] for candidate in listed] == [created["id"]]

    updated = await service.update_candidate(
        created["id"],
        MemoryCandidateUpdateRequest(
            payload={"title": "Move to Portugal next year"},
            reason="User corrected destination.",
        ),
    )

    assert updated["preview"] == "plan: Move to Portugal next year"
    assert updated["reason"] == "User corrected destination."


@pytest.mark.asyncio
async def test_approve_candidate_marks_approved_without_durable_write():
    repo = FakeMemoryCandidateRepository()
    service = MemoryCandidateService(repo)
    created = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="plan",
            payload={"title": "Launch Clarity"},
            risk_level="high",
        )
    )

    approved = await service.approve_candidate(
        created["id"],
        MemoryCandidateApproveRequest(approved_by="pedro", reason="Looks right."),
    )

    assert approved["status"] == "approved"
    assert approved["approved_by"] == "pedro"
    assert approved["decision"]["durable_apply_enabled"] is False
    assert repo.durable_writes == []


@pytest.mark.asyncio
async def test_reject_candidate_marks_rejected_without_durable_write():
    repo = FakeMemoryCandidateRepository()
    service = MemoryCandidateService(repo)
    created = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="commitment",
            payload={"title": "Review eligibility"},
            risk_level="low",
        )
    )

    rejected = await service.reject_candidate(
        created["id"],
        MemoryCandidateRejectRequest(reason="Not useful."),
    )

    assert rejected["status"] == "rejected"
    assert rejected["reason"] == "Not useful."
    assert repo.durable_writes == []


@pytest.mark.asyncio
async def test_bulk_approve_skips_high_risk_by_default():
    repo = FakeMemoryCandidateRepository()
    service = MemoryCandidateService(repo)
    low = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="commitment",
            payload={"title": "Prepare release build"},
            risk_level="low",
            source_conversation_id="conversation-1",
        )
    )
    high = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="archive",
            payload={"title": "Archive duplicate plans"},
            risk_level="high",
            source_conversation_id="conversation-1",
        )
    )

    result = await service.bulk_approve_candidates(
        MemoryCandidateBulkDecisionRequest(source_conversation_id="conversation-1")
    )

    assert [candidate["id"] for candidate in result["approved"]] == [low["id"]]
    assert [candidate["id"] for candidate in result["skipped"]] == [high["id"]]
    assert repo.candidates[0]["status"] == "approved"
    assert repo.candidates[1]["status"] == "pending"


@pytest.mark.asyncio
async def test_bulk_reject_rejects_selected_candidates():
    repo = FakeMemoryCandidateRepository()
    service = MemoryCandidateService(repo)
    first = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="entity_event",
            payload={"title": "Small note"},
            risk_level="low",
        )
    )
    second = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="entity_event",
            payload={"title": "Other note"},
            risk_level="low",
        )
    )

    result = await service.bulk_reject_candidates(
        MemoryCandidateBulkDecisionRequest(candidate_ids=[first["id"], second["id"]])
    )

    assert [candidate["status"] for candidate in result["rejected"]] == [
        "rejected",
        "rejected",
    ]


@pytest.mark.asyncio
async def test_service_maps_memory_errors():
    service = MemoryCandidateService(
        FakeMemoryCandidateRepository(MemoryServiceError("No database.", 503))
    )

    with pytest.raises(MemoryCandidateServiceError) as error:
        await service.list_candidates()

    assert error.value.detail == "No database."
    assert error.value.status_code == 503
