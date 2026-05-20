import pytest
from pydantic import ValidationError

from app.models.memory_discipline import (
    MemoryCandidateKind,
    MemoryDisciplineAction,
    MemoryDisciplineCandidate,
    MemoryDisciplineDecision,
    MemoryRelatedRecord,
)
from app.services.memory_discipline_service import (
    MemoryDisciplineService,
    normalized_similarity_score,
    title_similarity_score,
    token_overlap_score,
)


class FakeMemoryDisciplineRepository:
    def __init__(self):
        self.memories = []
        self.entities = []
        self.rules = []
        self.plans = []
        self.milestones = []
        self.commitments = []
        self.created_entities = []
        self.created_plans = []
        self.created_milestones = []
        self.created_commitments = []
        self.created_rules = []
        self.calls = []

    async def list_long_term_memory(self, limit=50, memory_type=None, active=None):
        self.calls.append(("list_long_term_memory", active, limit))
        return _filter_active(self.memories, active)[:limit]

    async def list_entities(
        self,
        limit=50,
        entity_type=None,
        status=None,
        active=None,
        normalized_name=None,
    ):
        self.calls.append(("list_entities", active, limit))
        rows = _filter_active(self.entities, active)
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if normalized_name is not None:
            rows = [
                row for row in rows if row.get("normalized_name") == normalized_name
            ]
        return rows[:limit]

    async def list_personal_rules(
        self,
        limit=50,
        rule_type=None,
        status=None,
        active=None,
    ):
        self.calls.append(("list_personal_rules", active, limit))
        return _filter_active(self.rules, active)[:limit]

    async def list_plans(self, limit=50, plan_type=None, status=None, active=None):
        self.calls.append(("list_plans", active, limit))
        rows = _filter_active(self.plans, active)
        if plan_type is not None:
            rows = [row for row in rows if row.get("plan_type") == plan_type]
        return rows[:limit]

    async def list_plan_milestones(
        self,
        limit=50,
        plan_id=None,
        status=None,
        active=None,
    ):
        self.calls.append(("list_plan_milestones", active, limit))
        return _filter_active(self.milestones, active)[:limit]

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
        self.calls.append(("list_commitments", active, limit))
        return _filter_active(self.commitments, active)[:limit]

    async def create_entity(self, payload):
        row = {"id": f"entity-{len(self.created_entities) + 1}", **payload}
        self.created_entities.append(row)
        self.entities.append(row)
        return row

    async def create_plan(self, payload):
        row = {"id": f"plan-{len(self.created_plans) + 1}", **payload}
        self.created_plans.append(row)
        self.plans.append(row)
        return row

    async def create_plan_milestone(self, payload):
        row = {"id": f"milestone-{len(self.created_milestones) + 1}", **payload}
        self.created_milestones.append(row)
        self.milestones.append(row)
        return row

    async def create_commitment(self, payload):
        row = {"id": f"commitment-{len(self.created_commitments) + 1}", **payload}
        self.created_commitments.append(row)
        self.commitments.append(row)
        return row

    async def create_personal_rule(self, payload):
        row = {"id": f"rule-{len(self.created_rules) + 1}", **payload}
        self.created_rules.append(row)
        self.rules.append(row)
        return row

    async def update_plan(self, plan_id, **updates):
        return _update(self.plans, plan_id, updates)


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


def test_memory_discipline_models_validate_action_values():
    decision = MemoryDisciplineDecision(
        action=MemoryDisciplineAction.CREATE_PLAN,
        candidate_kind=MemoryCandidateKind.PLAN,
        reason="new durable plan",
    )

    assert decision.action == MemoryDisciplineAction.CREATE_PLAN

    with pytest.raises(ValidationError):
        MemoryDisciplineDecision(
            action="make_random_thing",
            candidate_kind=MemoryCandidateKind.PLAN,
            reason="invalid",
        )


@pytest.mark.asyncio
async def test_gather_context_retrieves_related_active_records():
    repo = FakeMemoryDisciplineRepository()
    repo.plans.extend(
        [
            {
                "id": "plan-europe",
                "plan_type": "personal",
                "title": "Relocate to Europe next year",
                "description": "Build location independent income and savings.",
                "active": True,
            },
            {
                "id": "plan-health",
                "plan_type": "health",
                "title": "Gym routine",
                "description": "Lift weights three times per week.",
                "active": True,
            },
        ]
    )
    candidate = MemoryDisciplineCandidate(
        kind=MemoryCandidateKind.PLAN,
        payload={
            "plan_type": "finance",
            "title": "Reach 5k monthly income",
            "description": "Build location independent income for Europe.",
        },
    )

    context = await MemoryDisciplineService(repo).gather_context(candidate)

    assert ("list_plans", True, 100) in repo.calls
    assert context.active_plans[0]["id"] == "plan-europe"
    assert context.related_plans[0].id == "plan-europe"
    assert context.related_plans[0].score > 0.28
    assert all(record.id != "plan-health" for record in context.related_plans)


def test_matching_helpers_score_related_records_higher_than_unrelated_records():
    income = "Reach $5k monthly income with location independent work"
    europe = "Build location independent income before relocating to Europe"
    melissa = "Ask Melissa out for dinner next week"
    monday = "Monday date with Melissa outside of work"
    gym = "Leg day and protein target"

    assert token_overlap_score(income, europe) > token_overlap_score(income, gym)
    assert normalized_similarity_score(melissa, monday) > 0.35
    assert title_similarity_score(
        {"title": "Ask Melissa out for dinner"},
        {"title": "Ask Melissa out for dinner"},
    ) == 1


@pytest.mark.asyncio
async def test_plan_candidate_routes_to_milestone_under_existing_top_level_plan():
    repo = FakeMemoryDisciplineRepository()
    repo.plans.append(
        {
            "id": "plan-europe",
            "plan_type": "personal",
            "title": "Relocate to Europe next year",
            "description": "Build location independent income and savings.",
            "priority": 5,
            "active": True,
        }
    )
    candidate = MemoryDisciplineCandidate(
        kind=MemoryCandidateKind.PLAN,
        payload={
            "plan_type": "finance",
            "title": "Reach $5k monthly income",
            "description": "Build remote income to support Europe relocation.",
            "desired_outcome": "Stable income before moving.",
            "priority": 5,
        },
    )

    decision = await MemoryDisciplineService(repo).decide(candidate)

    assert decision.action == MemoryDisciplineAction.CREATE_MILESTONE
    assert decision.candidate_kind == MemoryCandidateKind.PLAN_MILESTONE
    assert decision.payload["plan_id"] == "plan-europe"
    assert decision.metadata["parent_plan_id"] == "plan-europe"


@pytest.mark.asyncio
async def test_plan_candidate_small_step_routes_to_commitment():
    repo = FakeMemoryDisciplineRepository()
    repo.plans.append(
        {
            "id": "plan-melissa",
            "plan_type": "dating",
            "title": "Ask Melissa out for dinner",
            "description": "Plan the date with Melissa.",
            "primary_entity_id": "person-melissa",
            "priority": 4,
            "active": True,
        }
    )
    candidate = MemoryDisciplineCandidate(
        kind=MemoryCandidateKind.PLAN,
        payload={
            "plan_type": "dating",
            "title": "Confirm Monday dinner time with Melissa",
            "description": "Text Melissa to lock the exact day and restaurant.",
            "primary_entity_id": "person-melissa",
            "priority": 4,
        },
    )

    decision = await MemoryDisciplineService(repo).decide(candidate)

    assert decision.action == MemoryDisciplineAction.CREATE_COMMITMENT
    assert decision.candidate_kind == MemoryCandidateKind.COMMITMENT
    assert decision.payload["plan_id"] == "plan-melissa"
    assert decision.payload["commitment_type"] == "relationship"


@pytest.mark.asyncio
async def test_decide_updates_strong_duplicate_same_kind_records():
    repo = FakeMemoryDisciplineRepository()
    repo.plans.append(
        {
            "id": "plan-melissa",
            "plan_type": "dating",
            "title": "Ask Melissa out for dinner",
            "description": "Dinner next week.",
            "active": True,
        }
    )
    service = MemoryDisciplineService(repo)
    candidate = MemoryDisciplineCandidate(
        kind=MemoryCandidateKind.PLAN,
        payload={
            "plan_type": "dating",
            "title": "Ask Melissa out for dinner",
            "description": "Dinner next week with a locked day.",
        },
    )

    decision = await service.decide(candidate)

    assert decision.action == MemoryDisciplineAction.UPDATE_PLAN
    assert decision.target_id == "plan-melissa"
    assert decision.metadata["discipline_version"] == 1
    assert decision.metadata["source_candidate_kind"] == "plan"


@pytest.mark.asyncio
async def test_apply_decision_writes_standard_metadata_on_updates():
    repo = FakeMemoryDisciplineRepository()
    repo.plans.append(
        {
            "id": "plan-1",
            "plan_type": "career",
            "title": "Ship Rex",
            "metadata": {"existing": True},
            "active": True,
        }
    )
    service = MemoryDisciplineService(repo)
    decision = MemoryDisciplineDecision(
        action=MemoryDisciplineAction.UPDATE_PLAN,
        candidate_kind=MemoryCandidateKind.PLAN,
        target_table="plans",
        target_id="plan-1",
        payload={"description": "Ship Rex and polish voice mode."},
        reason="duplicate plan update",
        related_records=[
            MemoryRelatedRecord(
                table="plans",
                id="plan-1",
                score=1,
                reason="test",
                record=repo.plans[0],
            )
        ],
        metadata={
            "discipline_version": 1,
            "discipline_action": "update_plan",
            "discipline_reason": "phase_1_foundation",
            "merged_from_id": None,
            "archived_by_correction_id": None,
            "canonical_entity_id": None,
            "source_candidate_kind": "plan",
            "requires_confirmation": False,
        },
    )

    result = await service.apply_decision(decision)

    assert result["applied"] is True
    assert repo.plans[0]["description"] == "Ship Rex and polish voice mode."
    assert repo.plans[0]["metadata"]["existing"] is True
    assert repo.plans[0]["metadata"]["discipline_action"] == "update_plan"


@pytest.mark.asyncio
async def test_apply_decision_creates_records_with_standard_metadata():
    repo = FakeMemoryDisciplineRepository()
    service = MemoryDisciplineService(repo)
    candidate = MemoryDisciplineCandidate(
        kind=MemoryCandidateKind.COMMITMENT,
        payload={
            "commitment_type": "work",
            "title": "Ship small piece",
            "commitment_text": "Ship one small Rex improvement today.",
        },
    )
    decision = await service.decide(candidate)

    result = await service.apply_decision(decision)

    assert result["applied"] is True
    assert repo.created_commitments[0]["metadata"]["discipline_action"] == (
        "create_commitment"
    )


@pytest.mark.asyncio
async def test_apply_decision_normalizes_obsolete_entity_references():
    repo = FakeMemoryDisciplineRepository()
    repo.entities.append(
        {
            "id": "entity-flowforce",
            "entity_type": "project",
            "display_name": "FlowForce",
            "normalized_name": "flowforce",
            "aliases": [],
            "metadata": {"obsolete_aliases": ["Flowfirst"]},
            "active": True,
        }
    )
    service = MemoryDisciplineService(repo)
    decision = MemoryDisciplineDecision(
        action=MemoryDisciplineAction.CREATE_PLAN,
        candidate_kind=MemoryCandidateKind.PLAN,
        payload={
            "plan_type": "career",
            "title": "Launch Flowfirst",
            "description": "Ship Flowfirst MVP.",
            "priority": 4,
        },
        reason="new plan",
        metadata={
            "discipline_version": 1,
            "discipline_action": "create_plan",
        },
    )

    result = await service.apply_decision(decision)

    assert result["applied"] is True
    assert repo.created_plans[0]["title"] == "Launch FlowForce"
    assert repo.created_plans[0]["description"] == "Ship FlowForce MVP."
    assert repo.created_plans[0]["primary_entity_id"] == "entity-flowforce"
