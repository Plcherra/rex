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
        self.entities = []
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

    async def list_entities(
        self,
        entity_type=None,
        normalized_name=None,
        status=None,
        active=True,
        limit=50,
    ):
        self._raise_if_configured()
        rows = self.entities
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if normalized_name is not None:
            rows = [
                row for row in rows if row.get("normalized_name") == normalized_name
            ]
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
async def test_plan_service_normalizes_obsolete_entity_references():
    memory = FakePlanMemoryService()
    memory.entities.append(
        {
            "id": "entity-flowforce",
            "entity_type": "project",
            "display_name": "FlowForce",
            "normalized_name": "flowforce",
            "aliases": [],
            "active": True,
            "status": "active",
            "metadata": {"obsolete_aliases": ["Flowfirst", "Flowforte"]},
        }
    )
    service = PlanService(memory)

    created = await service.create_plan(
        PlanCreateRequest(
            plan_type="career",
            title="Launch Flowfirst",
            description="Polish Flowforte and ship it.",
            desired_outcome="Revenue from Flowfirst.",
            priority=4,
        )
    )

    assert created["title"] == "Launch FlowForce"
    assert created["description"] == "Polish FlowForce and ship it."
    assert created["desired_outcome"] == "Revenue from FlowForce."
    assert created["primary_entity_id"] == "entity-flowforce"
    assert created["metadata"]["entity_normalization"][
        "canonical_entity_id"
    ] == "entity-flowforce"


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
            "primary_entity_id": None,
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
            primary_entity_id="entity-1",
            priority=5,
            metadata={"extracted": True},
        )
    )

    assert row["id"] == "plan-existing"
    assert row["desired_outcome"] == "Leave with enough financial runway."
    assert row["primary_entity_id"] == "entity-1"
    assert row["priority"] == 5
    assert row["metadata"] == {"source": "manual", "extracted": True}
    assert len(memory.plans) == 1


@pytest.mark.asyncio
async def test_plan_service_updates_wrong_name_plan_for_corrected_person():
    memory = FakePlanMemoryService()
    memory.plans.append(
        {
            "id": "plan-al",
            "plan_type": "dating",
            "title": "Ask Al out for dinner",
            "description": "Dinner with Al on Monday near my house.",
            "desired_outcome": "Successful date with Al.",
            "primary_entity_id": None,
            "priority": 4,
            "status": "active",
            "active": True,
            "metadata": {"source": "original"},
        }
    )
    service = PlanService(memory)

    row = await service.create_plan(
        PlanCreateRequest(
            plan_type="dating",
            title="Ask Melissa out for dinner",
            description="Dinner with Melissa on Monday near my house.",
            desired_outcome="Successful date with Melissa.",
            primary_entity_id="entity-melissa",
            priority=5,
            metadata={
                "source_content": (
                    "The person for the next-week date plan is Melissa, "
                    "corrected from Al or AI."
                )
            },
        )
    )

    assert row["id"] == "plan-al"
    assert row["title"] == "Ask Melissa out for dinner"
    assert row["description"] == "Dinner with Melissa on Monday near my house."
    assert row["desired_outcome"] == "Successful date with Melissa."
    assert row["primary_entity_id"] == "entity-melissa"
    assert row["priority"] == 5
    assert len(memory.plans) == 1


@pytest.mark.asyncio
async def test_plan_service_archives_stale_wrong_name_duplicate():
    memory = FakePlanMemoryService()
    memory.plans.extend(
        [
            {
                "id": "plan-melissa",
                "plan_type": "dating",
                "title": "Ask Melissa out for dinner",
                "description": "Dinner with Melissa.",
                "desired_outcome": "Successful date with Melissa.",
                "primary_entity_id": "entity-melissa",
                "priority": 4,
                "status": "active",
                "active": True,
                "metadata": {},
            },
            {
                "id": "plan-al",
                "plan_type": "dating",
                "title": "Ask Al out for dinner",
                "description": "Dinner with Al on Monday.",
                "desired_outcome": "Successful date with Al.",
                "primary_entity_id": None,
                "priority": 4,
                "status": "active",
                "active": True,
                "metadata": {},
            },
        ]
    )
    service = PlanService(memory)

    row = await service.create_plan(
        PlanCreateRequest(
            plan_type="dating",
            title="Ask Melissa out for dinner",
            description="Dinner with Melissa.",
            desired_outcome="Successful date with Melissa.",
            primary_entity_id="entity-melissa",
            priority=5,
            metadata={"wrong_names": ["Al", "AI"]},
        )
    )

    assert row["id"] == "plan-melissa"
    stale = next(plan for plan in memory.plans if plan["id"] == "plan-al")
    assert stale["active"] is False
    assert stale["status"] == "archived"
    assert stale["metadata"]["superseded_by_plan_id"] == "plan-melissa"
    assert stale["metadata"]["cleanup_reason"] == "explicit_person_correction"


@pytest.mark.asyncio
async def test_plan_service_merges_related_same_person_dating_plan():
    memory = FakePlanMemoryService()
    memory.plans.append(
        {
            "id": "plan-date",
            "plan_type": "dating",
            "title": "Date with Melissa next week",
            "description": "Take Melissa out next week.",
            "desired_outcome": "Successful date with locked-in details.",
            "primary_entity_id": "entity-melissa",
            "priority": 4,
            "status": "active",
            "active": True,
            "metadata": {"source": "first"},
        }
    )
    service = PlanService(memory)

    row = await service.create_plan(
        PlanCreateRequest(
            plan_type="dating",
            title="Monday date with Melissa",
            description="Confirm Monday dinner with Melissa.",
            desired_outcome="Clear confirmation for the date.",
            primary_entity_id="entity-melissa",
            priority=5,
            metadata={"source": "update"},
        )
    )

    assert row["id"] == "plan-date"
    assert row["title"] == "Monday date with Melissa"
    assert row["priority"] == 5
    assert row["metadata"]["source"] == "update"
    assert row["metadata"]["merge_reason"] == "related_active_plan"
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
