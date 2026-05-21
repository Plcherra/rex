import pytest

from app.services.memory_verification_service import MemoryVerificationService


class FakeVerificationRepository:
    def __init__(self):
        self.memories = []
        self.entities = []
        self.entity_events = []
        self.rules = []
        self.plans = []
        self.milestones = []
        self.commitments = []

    async def list_long_term_memory(self, limit=50, memory_type=None, active=None):
        return _active(self.memories, active)[:limit]

    async def list_entities(
        self,
        limit=50,
        entity_type=None,
        status=None,
        active=None,
        normalized_name=None,
    ):
        return _active(self.entities, active)[:limit]

    async def list_entity_events(
        self,
        limit=50,
        entity_id=None,
        event_type=None,
        active=None,
    ):
        return _active(self.entity_events, active)[:limit]

    async def list_personal_rules(
        self,
        limit=50,
        rule_type=None,
        status=None,
        active=None,
    ):
        return _active(self.rules, active)[:limit]

    async def list_plans(self, limit=50, plan_type=None, status=None, active=None):
        return _active(self.plans, active)[:limit]

    async def list_plan_milestones(
        self,
        limit=50,
        plan_id=None,
        status=None,
        active=None,
    ):
        return _active(self.milestones, active)[:limit]

    async def list_commitments(
        self,
        limit=50,
        commitment_type=None,
        plan_id=None,
        milestone_id=None,
        entity_id=None,
        status=None,
        active=None,
    ):
        return _active(self.commitments, active)[:limit]


def _active(rows, active):
    if active is None:
        return list(rows)
    return [row for row in rows if row.get("active", True) is active]


@pytest.mark.asyncio
async def test_verify_applied_record_passes_when_active_record_is_readable():
    repo = FakeVerificationRepository()
    repo.plans.append(
        {
            "id": "plan-1",
            "title": "Move out of the country next year",
            "active": True,
        }
    )

    result = await MemoryVerificationService(repo).verify_applied_record(
        table="plans",
        record_id="plan-1",
    )

    assert result["passed"] is True
    assert result["applied_record"]["title"] == "Move out of the country next year"


@pytest.mark.asyncio
async def test_verify_applied_record_fails_when_record_is_not_readable():
    repo = FakeVerificationRepository()
    repo.plans.append(
        {
            "id": "plan-1",
            "title": "Archived plan",
            "active": False,
        }
    )

    result = await MemoryVerificationService(repo).verify_applied_record(
        table="plans",
        record_id="plan-1",
    )

    assert result["passed"] is False
    assert result["message"] == (
        "Candidate apply returned a record id, but the active record was not readable."
    )


@pytest.mark.asyncio
async def test_verify_correction_passes_when_no_active_stale_terms_remain():
    repo = FakeVerificationRepository()
    repo.plans.append(
        {
            "id": "plan-1",
            "title": "Launch FlowForce",
            "description": "Correct app name.",
            "active": True,
        }
    )

    result = await MemoryVerificationService(repo).verify_correction(
        stale_terms=["Flowfirst"],
        applied_record={"table": "memory_corrections", "id": "correction-1"},
    )

    assert result["passed"] is True
    assert "plans" in result["checked_tables"]
    assert result["remaining_conflicts"] == []


@pytest.mark.asyncio
async def test_verify_correction_reports_remaining_active_stale_records():
    repo = FakeVerificationRepository()
    repo.entities.append(
        {
            "id": "entity-1",
            "display_name": "Stephanie",
            "summary": "Stephanie got fired at the beginning of this year.",
            "active": True,
        }
    )
    repo.entities.append(
        {
            "id": "entity-2",
            "display_name": "Archived Stephanie",
            "summary": "Stephanie got fired at the beginning of this year.",
            "active": False,
        }
    )

    result = await MemoryVerificationService(repo).verify_correction(
        stale_terms=["Stephanie got fired"],
    )

    assert result["passed"] is False
    assert result["remaining_conflicts"] == [
        {
            "table": "entities",
            "id": "entity-1",
            "title": "Stephanie",
            "matched_terms": ["stephanie got fired"],
        }
    ]
