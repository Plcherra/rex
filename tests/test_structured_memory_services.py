import pytest

from app.models.commitment import CommitmentCreateRequest, CommitmentUpdateRequest
from app.models.entity import EntityCreateRequest, EntityUpdateRequest
from app.models.personal_rule import PersonalRuleCreateRequest
from app.models.plan import PlanCreateRequest, PlanMilestoneCreateRequest
from app.services.commitment_service import CommitmentService, CommitmentServiceError
from app.services.entity_service import EntityService, EntityServiceError
from app.services.plan_service import PlanService
from app.services.rule_service import RuleService


class FakeStructuredMemoryRepository:
    def __init__(self) -> None:
        self.entities = []
        self.rules = []
        self.plans = []
        self.milestones = []
        self.commitments = []
        self.created_entities = []
        self.created_rules = []
        self.created_plans = []
        self.created_milestones = []
        self.created_commitments = []

    async def create_entity(self, payload):
        row = {"id": f"entity-{len(self.created_entities) + 1}", **payload}
        self.created_entities.append(row)
        self.entities.append(row)
        return row

    async def list_entities(
        self, *, entity_type=None, normalized_name=None, active=True, limit=50
    ):
        rows = self.entities
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if normalized_name is not None:
            rows = [
                row for row in rows if row.get("normalized_name") == normalized_name
            ]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_entity(self, entity_id, **payload):
        return _update(self.entities, entity_id, payload)

    async def deactivate_entity(self, entity_id):
        return await self.update_entity(entity_id, active=False, status="inactive")

    async def create_personal_rule(self, payload):
        row = {"id": f"rule-{len(self.created_rules) + 1}", **payload}
        self.created_rules.append(row)
        self.rules.append(row)
        return row

    async def list_personal_rules(
        self, *, rule_type=None, status=None, active=True, limit=50
    ):
        rows = self.rules
        if rule_type is not None:
            rows = [row for row in rows if row.get("rule_type") == rule_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_personal_rule(self, rule_id, **payload):
        return _update(self.rules, rule_id, payload)

    async def deactivate_personal_rule(self, rule_id):
        return await self.update_personal_rule(rule_id, active=False, status="archived")

    async def create_plan(self, payload):
        row = {"id": f"plan-{len(self.created_plans) + 1}", **payload}
        self.created_plans.append(row)
        self.plans.append(row)
        return row

    async def list_plans(self, *, plan_type=None, status=None, active=True, limit=50):
        rows = self.plans
        if plan_type is not None:
            rows = [row for row in rows if row.get("plan_type") == plan_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_plan(self, plan_id, **payload):
        return _update(self.plans, plan_id, payload)

    async def deactivate_plan(self, plan_id):
        return await self.update_plan(plan_id, active=False, status="archived")

    async def create_plan_milestone(self, payload):
        row = {"id": f"milestone-{len(self.created_milestones) + 1}", **payload}
        self.created_milestones.append(row)
        self.milestones.append(row)
        return row

    async def list_plan_milestones(
        self, *, plan_id=None, status=None, active=True, limit=50
    ):
        rows = self.milestones
        if plan_id is not None:
            rows = [row for row in rows if row.get("plan_id") == plan_id]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def create_commitment(self, payload):
        row = {"id": f"commitment-{len(self.created_commitments) + 1}", **payload}
        self.created_commitments.append(row)
        self.commitments.append(row)
        return row

    async def list_commitments(
        self, *, commitment_type=None, status=None, active=True, limit=50
    ):
        rows = self.commitments
        if commitment_type is not None:
            rows = [
                row for row in rows if row.get("commitment_type") == commitment_type
            ]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_commitment(self, commitment_id, **payload):
        return _update(self.commitments, commitment_id, payload)

    async def deactivate_commitment(self, commitment_id):
        return await self.update_commitment(
            commitment_id, active=False, status="archived"
        )


def _update(rows, row_id, payload):
    for row in rows:
        if row["id"] == row_id:
            row.update(payload)
            return row
    return None


@pytest.mark.asyncio
async def test_entity_service_normalizes_and_creates_entity():
    repo = FakeStructuredMemoryRepository()
    service = EntityService(repo)

    row = await service.create_entity(
        EntityCreateRequest(
            entity_type="person",
            display_name="  Pedro   Martins ",
            normalized_name="Pedro Martins",
            aliases=["Pedro", "pedro", "  PM  "],
        )
    )

    assert row["display_name"] == "Pedro Martins"
    assert row["normalized_name"] == "pedro martins"
    assert row["aliases"] == ["Pedro", "PM"]
    assert repo.created_entities == [row]


@pytest.mark.asyncio
async def test_entity_service_deduplicates_existing_entity():
    repo = FakeStructuredMemoryRepository()
    repo.entities.append(
        {
            "id": "entity-1",
            "entity_type": "person",
            "display_name": "Pedro Martins",
            "normalized_name": "pedro martins",
            "aliases": ["Pedro"],
            "importance": 2,
            "active": True,
            "metadata": {"source": "old"},
        }
    )
    service = EntityService(repo)

    row = await service.create_entity(
        EntityCreateRequest(
            entity_type="person",
            display_name="Pedro Martins",
            normalized_name="Pedro Martins",
            aliases=["PM"],
            importance=5,
            metadata={"new": True},
        )
    )

    assert row["id"] == "entity-1"
    assert row["aliases"] == ["Pedro", "PM"]
    assert row["importance"] == 5
    assert row["metadata"] == {"source": "old", "new": True}
    assert repo.created_entities == []


@pytest.mark.asyncio
async def test_entity_service_deduplicates_descriptive_mentions_and_aliases():
    repo = FakeStructuredMemoryRepository()
    repo.entities.append(
        {
            "id": "entity-1",
            "entity_type": "person",
            "display_name": "Clara",
            "normalized_name": "clara",
            "aliases": ["Clara"],
            "importance": 3,
            "active": True,
            "metadata": {},
        }
    )
    service = EntityService(repo)

    row = await service.create_entity(
        EntityCreateRequest(
            entity_type="person",
            display_name="the girl Clara",
            normalized_name="Clara from work",
            aliases=["Clara from work"],
            summary="Clara is someone the user knows from work.",
            importance=4,
        )
    )

    assert row["id"] == "entity-1"
    assert row["aliases"] == ["Clara", "Clara from work", "the girl Clara"]
    assert row["summary"] == "Clara is someone the user knows from work."
    assert row["importance"] == 4
    assert repo.created_entities == []


@pytest.mark.asyncio
async def test_entity_service_update_missing_entity_raises_not_found():
    service = EntityService(FakeStructuredMemoryRepository())

    with pytest.raises(EntityServiceError) as error:
        await service.update_entity(
            "missing",
            EntityUpdateRequest(summary="Still not there."),
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_rule_service_deduplicates_by_rule_text():
    repo = FakeStructuredMemoryRepository()
    repo.rules.append(
        {
            "id": "rule-1",
            "rule_type": "food_delivery",
            "title": "No DoorDash",
            "rule_text": "No DoorDash this month.",
            "trigger_keywords": ["DoorDash"],
            "priority": 2,
            "active": True,
            "metadata": {},
        }
    )
    service = RuleService(repo)

    row = await service.create_rule(
        PersonalRuleCreateRequest(
            rule_type="food_delivery",
            title="No delivery",
            rule_text=" no doordash this month. ",
            trigger_keywords=["Uber Eats"],
            priority=4,
        )
    )

    assert row["id"] == "rule-1"
    assert row["trigger_keywords"] == ["DoorDash", "Uber Eats"]
    assert row["priority"] == 4
    assert repo.created_rules == []


@pytest.mark.asyncio
async def test_plan_service_deduplicates_plans_and_creates_milestones():
    repo = FakeStructuredMemoryRepository()
    repo.plans.append(
        {
            "id": "plan-1",
            "plan_type": "immigration",
            "title": "Move abroad",
            "priority": 2,
            "active": True,
            "metadata": {},
        }
    )
    service = PlanService(repo)

    plan = await service.create_plan(
        PlanCreateRequest(
            plan_type="immigration",
            title=" Move   Abroad ",
            desired_outcome="Leave with enough runway.",
            priority=5,
        )
    )
    milestone = await service.create_milestone(
        PlanMilestoneCreateRequest(
            plan_id=plan["id"],
            title="  Save first target ",
            milestone_type="goal",
        )
    )

    assert plan["id"] == "plan-1"
    assert plan["desired_outcome"] == "Leave with enough runway."
    assert repo.created_plans == []
    assert milestone["title"] == "Save first target"
    assert milestone["plan_id"] == "plan-1"


@pytest.mark.asyncio
async def test_commitment_service_deduplicates_open_commitments():
    repo = FakeStructuredMemoryRepository()
    repo.commitments.append(
        {
            "id": "commitment-1",
            "commitment_type": "health",
            "title": "Gym",
            "commitment_text": "Work out tomorrow morning.",
            "status": "open",
            "active": True,
            "plan_id": None,
            "entity_id": None,
            "priority": 2,
            "metadata": {},
        }
    )
    service = CommitmentService(repo)

    row = await service.create_commitment(
        CommitmentCreateRequest(
            commitment_type="health",
            title="Workout",
            commitment_text=" work out tomorrow morning. ",
            priority=5,
            due_at="2026-05-18T12:00:00Z",
        )
    )

    assert row["id"] == "commitment-1"
    assert row["priority"] == 5
    assert row["due_at"] == "2026-05-18T12:00:00Z"
    assert repo.created_commitments == []


@pytest.mark.asyncio
async def test_commitment_service_deactivate_missing_raises_not_found():
    service = CommitmentService(FakeStructuredMemoryRepository())

    with pytest.raises(CommitmentServiceError) as error:
        await service.deactivate_commitment("missing")

    assert error.value.status_code == 404
