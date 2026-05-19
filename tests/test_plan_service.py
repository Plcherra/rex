import pytest
from pydantic import ValidationError

from app.models.plan import (
    PlanCreateRequest,
    PlanMilestoneCreateRequest,
    PlanMilestoneUpdateRequest,
    PlanUpdateRequest,
)
from app.services.memory_service import MemoryServiceError
from app.services.plan_service import PlanService, PlanServiceError


class FakePlanMemoryService:
    def __init__(self, error=None):
        self.error = error
        self.plans = []
        self.milestones = []

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def create_plan(self, payload):
        self._raise_if_configured()
        row = {"id": f"plan-{len(self.plans) + 1}", **payload}
        self.plans.append(row)
        return row

    async def list_plans(self, plan_type=None, status=None, active=True, limit=50):
        self._raise_if_configured()
        rows = self.plans
        if plan_type is not None:
            rows = [row for row in rows if row.get("plan_type") == plan_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_plan(self, plan_id, **updates):
        self._raise_if_configured()
        for row in self.plans:
            if row["id"] == plan_id:
                row.update(updates)
                return row
        return None

    async def deactivate_plan(self, plan_id):
        return await self.update_plan(plan_id, active=False, status="archived")

    async def create_plan_milestone(self, payload):
        self._raise_if_configured()
        row = {"id": f"milestone-{len(self.milestones) + 1}", **payload}
        self.milestones.append(row)
        return row

    async def list_plan_milestones(
        self,
        plan_id=None,
        status=None,
        active=True,
        limit=50,
    ):
        self._raise_if_configured()
        rows = self.milestones
        if plan_id is not None:
            rows = [row for row in rows if row.get("plan_id") == plan_id]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_plan_milestone(self, milestone_id, **updates):
        self._raise_if_configured()
        for row in self.milestones:
            if row["id"] == milestone_id:
                row.update(updates)
                return row
        return None

    async def deactivate_plan_milestone(self, milestone_id):
        return await self.update_plan_milestone(
            milestone_id,
            active=False,
            status="canceled",
        )


def test_plan_models_reject_invalid_schema_values():
    with pytest.raises(ValidationError):
        PlanCreateRequest(plan_type="visa", title="Move abroad")

    with pytest.raises(ValidationError):
        PlanCreateRequest(plan_type="immigration", title="Move abroad", priority=6)

    with pytest.raises(ValidationError):
        PlanMilestoneCreateRequest(
            plan_id="plan-1",
            title="Submit documents",
            milestone_type="meeting",
        )


@pytest.mark.asyncio
async def test_plan_create_update_deactivate_and_active_listing_flow():
    memory = FakePlanMemoryService()
    service = PlanService(memory)

    created = await service.create_plan(
        PlanCreateRequest(
            plan_type="immigration",
            title="  Move   Abroad ",
            description="  leave the country legally ",
            desired_outcome="  clean paperwork and enough runway ",
            priority=4,
            target_date="2026-07-01",
        )
    )

    assert created["title"] == "Move Abroad"
    assert created["description"] == "leave the country legally"
    assert created["desired_outcome"] == "clean paperwork and enough runway"

    active_plans = await service.list_plans(plan_type="immigration", status="active")
    assert active_plans == [created]

    updated = await service.update_plan(
        created["id"],
        PlanUpdateRequest(status="paused", priority=5),
    )
    assert updated["status"] == "paused"
    assert updated["priority"] == 5

    deactivated = await service.deactivate_plan(created["id"])
    assert deactivated["active"] is False
    assert deactivated["status"] == "archived"
    assert await service.list_plans(active=True) == []


@pytest.mark.asyncio
async def test_plan_service_deduplicates_active_plan_by_title_and_type():
    memory = FakePlanMemoryService()
    memory.plans.append(
        {
            "id": "plan-existing",
            "plan_type": "immigration",
            "title": "Move abroad",
            "description": None,
            "desired_outcome": None,
            "priority": 2,
            "status": "active",
            "active": True,
            "metadata": {"source": "manual"},
        }
    )
    service = PlanService(memory)

    row = await service.create_plan(
        PlanCreateRequest(
            plan_type="immigration",
            title=" move   abroad ",
            desired_outcome="Leave with enough financial runway.",
            priority=5,
            metadata={"extracted": True},
        )
    )

    assert row["id"] == "plan-existing"
    assert row["desired_outcome"] == "Leave with enough financial runway."
    assert row["priority"] == 5
    assert row["metadata"] == {"source": "manual", "extracted": True}
    assert len(memory.plans) == 1


@pytest.mark.asyncio
async def test_plan_milestone_create_update_deactivate_flow():
    memory = FakePlanMemoryService()
    service = PlanService(memory)

    milestone = await service.create_milestone(
        PlanMilestoneCreateRequest(
            plan_id="plan-1",
            title="  Submit   documents ",
            description=" collect all visa files ",
            milestone_type="deadline",
            target_date="2026-06-01",
        )
    )

    assert milestone["title"] == "Submit documents"
    assert milestone["description"] == "collect all visa files"

    listed = await service.list_milestones(plan_id="plan-1", status="open")
    assert listed == [milestone]

    updated = await service.update_milestone(
        milestone["id"],
        PlanMilestoneUpdateRequest(status="in_progress", priority=5),
    )
    assert updated["status"] == "in_progress"
    assert updated["priority"] == 5

    deactivated = await service.deactivate_milestone(milestone["id"])
    assert deactivated["active"] is False
    assert deactivated["status"] == "canceled"


@pytest.mark.asyncio
async def test_plan_service_failure_paths_do_not_call_supabase():
    service = PlanService(FakePlanMemoryService())

    with pytest.raises(PlanServiceError) as missing_plan:
        await service.update_plan("missing", PlanUpdateRequest(priority=5))
    assert missing_plan.value.status_code == 404

    with pytest.raises(PlanServiceError) as missing_milestone:
        await service.update_milestone(
            "missing",
            PlanMilestoneUpdateRequest(status="completed"),
        )
    assert missing_milestone.value.status_code == 404

    failing_service = PlanService(
        FakePlanMemoryService(MemoryServiceError("Cannot reach memory.", 503))
    )
    with pytest.raises(PlanServiceError) as repo_error:
        await failing_service.list_plans()
    assert repo_error.value.detail == "Cannot reach memory."
    assert repo_error.value.status_code == 503
