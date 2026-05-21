import pytest

from app.models.memory_discipline import (
    MemoryCandidateKind,
    MemoryDisciplineAction,
    MemoryDisciplineCandidate,
    MemoryDisciplineDecision,
)
from app.services.memory_discipline_service import MemoryDisciplineService


class RegressionMemoryRepo:
    def __init__(self):
        self.entities = []
        self.rules = []
        self.plans = []
        self.milestones = []
        self.commitments = []
        self.archived_entities = []

    async def list_long_term_memory(self, **kwargs):
        return []

    async def list_entities(self, **kwargs):
        return self.entities

    async def list_personal_rules(self, **kwargs):
        return self.rules

    async def list_plans(self, **kwargs):
        return self.plans

    async def list_plan_milestones(self, **kwargs):
        return self.milestones

    async def list_commitments(self, **kwargs):
        return self.commitments

    async def update_entity(self, entity_id, **updates):
        return _update(self.entities, entity_id, updates)

    async def update_personal_rule(self, rule_id, **updates):
        return _update(self.rules, rule_id, updates)

    async def create_plan_milestone(self, payload):
        row = {"id": f"milestone-{len(self.milestones) + 1}", **payload}
        self.milestones.append(row)
        return row

    async def create_commitment(self, payload):
        row = {"id": f"commitment-{len(self.commitments) + 1}", **payload}
        self.commitments.append(row)
        return row

    async def deactivate_entity(self, entity_id):
        self.archived_entities.append(entity_id)
        for entity in self.entities:
            if entity["id"] == entity_id:
                entity["active"] = False
                return True
        return False


def _update(rows, row_id, updates):
    for row in rows:
        if row["id"] == row_id:
            row.update(updates)
            return row
    return None


@pytest.mark.asyncio
async def test_income_goal_routes_under_europe_plan_instead_of_new_plan():
    repo = RegressionMemoryRepo()
    repo.plans.append(
        {
            "id": "plan-europe",
            "plan_type": "personal",
            "title": "Relocate to Europe next year",
            "description": "Move with stable location-independent income.",
            "status": "active",
            "active": True,
            "priority": 5,
        }
    )
    service = MemoryDisciplineService(repo)

    decision = await service.decide(
        MemoryDisciplineCandidate(
            kind=MemoryCandidateKind.PLAN,
            payload={
                "plan_type": "finance",
                "title": "$5k monthly revenue target",
                "description": "Reach $5k monthly revenue before moving to Europe.",
                "desired_outcome": "Location-independent income.",
                "priority": 5,
            },
        )
    )

    assert decision.action == MemoryDisciplineAction.CREATE_MILESTONE
    applied = await service.apply_decision(decision)
    assert applied["record"]["plan_id"] == "plan-europe"


@pytest.mark.asyncio
async def test_duplicate_dating_plan_does_not_create_new_top_level_plan():
    repo = RegressionMemoryRepo()
    repo.plans.append(
        {
            "id": "plan-melissa",
            "plan_type": "dating",
            "title": "Ask Melissa out for dinner",
            "description": "Plan dinner with Melissa next week.",
            "status": "active",
            "active": True,
        }
    )
    service = MemoryDisciplineService(repo)

    decision = await service.decide(
        MemoryDisciplineCandidate(
            kind=MemoryCandidateKind.PLAN,
            payload={
                "plan_type": "dating",
                "title": "Date with Melissa next week",
                "description": "Take Melissa to dinner next week.",
                "desired_outcome": "Successful date with Melissa.",
                "priority": 4,
            },
        )
    )

    assert decision.action != MemoryDisciplineAction.CREATE_PLAN
    assert decision.action in {
        MemoryDisciplineAction.CREATE_COMMITMENT,
        MemoryDisciplineAction.UPDATE_PLAN,
    }


@pytest.mark.asyncio
async def test_direct_duplicate_milestone_updates_existing_milestone():
    repo = RegressionMemoryRepo()
    repo.plans.append(
        {
            "id": "plan-europe",
            "plan_type": "personal",
            "title": "Move out of the country next year",
            "description": "Move after reaching stable income.",
            "status": "active",
            "active": True,
            "priority": 5,
        }
    )
    repo.milestones.append(
        {
            "id": "milestone-income",
            "plan_id": "plan-europe",
            "title": "Reach $5k monthly income",
            "description": "Reach stable income before moving.",
            "status": "open",
            "active": True,
        }
    )

    decision = await MemoryDisciplineService(repo).decide(
        MemoryDisciplineCandidate(
            kind=MemoryCandidateKind.PLAN_MILESTONE,
            payload={
                "plan_id": "plan-europe",
                "title": "$5k monthly revenue target",
                "description": "Reach $5k/month before moving out.",
            },
        )
    )

    assert decision.action == MemoryDisciplineAction.UPDATE_MILESTONE
    assert decision.target_id == "milestone-income"


@pytest.mark.asyncio
async def test_project_name_drift_updates_canonical_entity():
    repo = RegressionMemoryRepo()
    repo.entities.append(
        {
            "id": "entity-flowforce",
            "entity_type": "project",
            "display_name": "FlowForce",
            "normalized_name": "flowforce",
            "aliases": ["Flowfirst", "Flowforte"],
            "status": "active",
            "active": True,
            "metadata": {},
        }
    )
    service = MemoryDisciplineService(repo)

    decision = await service.decide(
        MemoryDisciplineCandidate(
            kind=MemoryCandidateKind.ENTITY,
            payload={
                "entity_type": "project",
                "display_name": "Flowfirst",
                "normalized_name": "flowfirst",
                "summary": "Project mentioned by the user.",
                "importance": 4,
            },
        )
    )
    applied = await service.apply_decision(decision)

    assert decision.action == MemoryDisciplineAction.UPDATE_ENTITY
    assert applied["record"]["display_name"] == "FlowForce"
    assert applied["record"]["normalized_name"] == "flowforce"


@pytest.mark.asyncio
async def test_duplicate_rule_updates_existing_rule():
    repo = RegressionMemoryRepo()
    repo.rules.append(
        {
            "id": "rule-delivery",
            "rule_type": "food_delivery",
            "title": "No Uber or DoorDash",
            "rule_text": "Do not use Uber or DoorDash.",
            "status": "active",
            "active": True,
        }
    )
    service = MemoryDisciplineService(repo)

    decision = await service.decide(
        MemoryDisciplineCandidate(
            kind=MemoryCandidateKind.PERSONAL_RULE,
            payload={
                "rule_type": "food_delivery",
                "title": "No Uber or DoorDash",
                "rule_text": "Avoid spending on Uber or DoorDash.",
                "priority": 4,
            },
        )
    )

    assert decision.action == MemoryDisciplineAction.UPDATE_RULE


@pytest.mark.asyncio
async def test_small_task_misclassified_as_plan_becomes_commitment():
    repo = RegressionMemoryRepo()
    repo.plans.append(
        {
            "id": "plan-apps",
            "plan_type": "career",
            "title": "Three-month app development plan",
            "description": "Ship EchoDesk and FlowForce.",
            "status": "active",
            "active": True,
        }
    )
    service = MemoryDisciplineService(repo)

    decision = await service.decide(
        MemoryDisciplineCandidate(
            kind=MemoryCandidateKind.PLAN,
            payload={
                "plan_type": "career",
                "title": "Email FlowForce lead",
                "description": "Email the first FlowForce lead tomorrow.",
                "priority": 4,
            },
        )
    )

    assert decision.action == MemoryDisciplineAction.CREATE_COMMITMENT
    applied = await service.apply_decision(decision)
    assert applied["record"]["plan_id"] == "plan-apps"


@pytest.mark.asyncio
async def test_correction_workflow_can_archive_stale_entity():
    repo = RegressionMemoryRepo()
    repo.entities.append(
        {
            "id": "entity-stale",
            "entity_type": "person",
            "display_name": "Al",
            "status": "active",
            "active": True,
        }
    )
    service = MemoryDisciplineService(repo)

    applied = await service.apply_decision(
        MemoryDisciplineDecision(
            action=MemoryDisciplineAction.ARCHIVE_ENTITY,
            candidate_kind=MemoryCandidateKind.ENTITY,
            payload={},
            reason="Stale corrected entity should not stay active.",
            target_id="entity-stale",
        )
    )

    assert applied["applied"] is True
    assert repo.entities[0]["active"] is False
