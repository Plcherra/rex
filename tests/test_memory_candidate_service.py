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
        self.memories = []
        self.entities = []
        self.entity_events = []
        self.rules = []
        self.plans = []
        self.milestones = []
        self.commitments = []
        self.corrections = []

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
        row = {"id": "plan-1", "active": True, **payload}
        self.plans.append(row)
        return row

    async def create_commitment(self, payload):
        self.durable_writes.append(("commitments", payload))
        row = {"id": "commitment-1", "active": True, **payload}
        self.commitments.append(row)
        return row

    async def create_plan_milestone(self, payload):
        self.durable_writes.append(("plan_milestones", payload))
        row = {"id": "milestone-1", "active": True, **payload}
        self.milestones.append(row)
        return row

    async def create_entity(self, payload):
        self.durable_writes.append(("entities", payload))
        row = {"id": "entity-1", "active": True, **payload}
        self.entities.append(row)
        return row

    async def create_personal_rule(self, payload):
        self.durable_writes.append(("personal_rules", payload))
        row = {"id": "rule-1", "active": True, **payload}
        self.rules.append(row)
        return row

    async def save_long_term_memory(self, **payload):
        self.durable_writes.append(("long_term_memory", payload))
        row = {"id": "memory-1", "active": True, **payload}
        self.memories.append(row)
        return row

    async def create_entity_event(self, payload):
        self.durable_writes.append(("entity_events", payload))
        row = {"id": "event-1", "active": True, **payload}
        self.entity_events.append(row)
        return row

    async def list_long_term_memory(self, **kwargs):
        return _filter_active(self.memories, kwargs.get("active"))

    async def list_entities(self, **kwargs):
        return _filter_active(self.entities, kwargs.get("active"))

    async def list_entity_events(self, **kwargs):
        return _filter_active(self.entity_events, kwargs.get("active"))

    async def list_personal_rules(self, **kwargs):
        return _filter_active(self.rules, kwargs.get("active"))

    async def list_plans(self, **kwargs):
        return _filter_active(self.plans, kwargs.get("active"))

    async def list_plan_milestones(self, **kwargs):
        return _filter_active(self.milestones, kwargs.get("active"))

    async def list_commitments(self, **kwargs):
        return _filter_active(self.commitments, kwargs.get("active"))

    async def update_long_term_memory(self, memory_id, **updates):
        return _update(self.memories, memory_id, updates)

    async def update_entity(self, entity_id, **updates):
        return _update(self.entities, entity_id, updates)

    async def update_entity_event(self, event_id, **updates):
        return _update(self.entity_events, event_id, updates)

    async def update_personal_rule(self, rule_id, **updates):
        return _update(self.rules, rule_id, updates)

    async def update_plan(self, plan_id, **updates):
        return _update(self.plans, plan_id, updates)

    async def update_plan_milestone(self, milestone_id, **updates):
        return _update(self.milestones, milestone_id, updates)

    async def update_commitment(self, commitment_id, **updates):
        return _update(self.commitments, commitment_id, updates)

    async def deactivate_long_term_memory(self, memory_id):
        return _deactivate(self.memories, memory_id)

    async def deactivate_entity(self, entity_id):
        return _deactivate(self.entities, entity_id, status="inactive")

    async def deactivate_entity_event(self, event_id):
        return _deactivate(self.entity_events, event_id)

    async def deactivate_personal_rule(self, rule_id):
        return _deactivate(self.rules, rule_id, status="archived")

    async def deactivate_plan(self, plan_id):
        return _deactivate(self.plans, plan_id, status="archived")

    async def deactivate_plan_milestone(self, milestone_id):
        return _deactivate(self.milestones, milestone_id, status="canceled")

    async def deactivate_commitment(self, commitment_id):
        return _deactivate(self.commitments, commitment_id, status="archived")

    async def create_memory_correction(self, correction):
        row = {"id": f"correction-{len(self.corrections) + 1}", **correction}
        self.corrections.append(row)
        return row


def _filter_active(rows, active):
    if active is None:
        return list(rows)
    return [row for row in rows if row.get("active", True) is active]


def _update(rows, row_id, updates):
    for row in rows:
        if row.get("id") == row_id:
            row.update(updates)
            return row
    return None


def _deactivate(rows, row_id, status=None):
    updates = {"active": False}
    if status is not None:
        updates["status"] = status
    return _update(rows, row_id, updates) is not None


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
async def test_approve_candidate_applies_durable_write():
    repo = FakeMemoryCandidateRepository()
    service = MemoryCandidateService(repo)
    created = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="plan",
            payload={
                "title": "Launch Clarity",
                "description": "Launch Clarity as the first confirmed app release.",
            },
            risk_level="high",
        )
    )

    approved = await service.approve_candidate(
        created["id"],
        MemoryCandidateApproveRequest(approved_by="pedro", reason="Looks right."),
    )

    assert approved["status"] == "applied"
    assert approved["approved_by"] == "pedro"
    assert approved["decision"]["durable_apply_enabled"] is True
    assert approved["verification"]["passed"] is True
    assert repo.durable_writes[0][0] == "plans"


@pytest.mark.asyncio
async def test_approve_correction_candidate_applies_and_verifies_stale_terms_removed():
    repo = FakeMemoryCandidateRepository()
    repo.plans.append(
        {
            "id": "plan-1",
            "title": "Launch Flowfirst",
            "description": "Flowfirst is the wrong app name.",
            "active": True,
            "metadata": {},
        }
    )
    service = MemoryCandidateService(repo)
    created = await service.create_candidate(
        MemoryCandidateCreateRequest(
            candidate_type="correction",
            payload={"text": "not Flowfirst, it is FlowForce"},
            risk_level="high",
        )
    )

    approved = await service.approve_candidate(
        created["id"],
        MemoryCandidateApproveRequest(approved_by="pedro"),
    )

    assert approved["status"] == "applied"
    assert repo.plans[0]["title"] == "Launch FlowForce"
    assert repo.corrections[0]["old_value"] == "Flowfirst"
    assert approved["verification"]["passed"] is True
    assert approved["verification"]["remaining_conflicts"] == []


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
            payload={
                "commitment_type": "task",
                "title": "Prepare release build",
                "commitment_text": "Prepare the release build.",
            },
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
    assert repo.candidates[0]["status"] == "applied"
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
