import pytest

from backend.scripts.cleanup_rex_brain_v2_current_data import (
    APP_PLAN_TITLE,
    MELISSA_PLAN_TITLE,
    RELOCATION_PLAN_TITLE,
    build_cleanup_operations,
    cleanup_rex_brain_v2_current_data,
    verify_cleanup_state,
)


class FakeCleanupMemoryService:
    def __init__(self):
        self.plans = []
        self.milestones = []
        self.commitments = []
        self.entities = []

    async def list_plans(self, **kwargs):
        return _filtered(self.plans, **kwargs)

    async def list_plan_milestones(self, **kwargs):
        return _filtered(self.milestones, **kwargs)

    async def list_commitments(self, **kwargs):
        return _filtered(self.commitments, **kwargs)

    async def list_entities(self, **kwargs):
        return _filtered(self.entities, **kwargs)

    async def update_plan(self, plan_id, **updates):
        return _update(self.plans, plan_id, updates)

    async def create_plan(self, payload):
        row = {"id": f"plan-created-{len(self.plans) + 1}", **payload}
        self.plans.append(row)
        return row

    async def create_plan_milestone(self, payload):
        row = {"id": f"milestone-created-{len(self.milestones) + 1}", **payload}
        self.milestones.append(row)
        return row

    async def update_plan_milestone(self, milestone_id, **updates):
        return _update(self.milestones, milestone_id, updates)

    async def update_commitment(self, commitment_id, **updates):
        return _update(self.commitments, commitment_id, updates)

    async def update_entity(self, entity_id, **updates):
        return _update(self.entities, entity_id, updates)


class FailingMilestoneCleanupMemoryService(FakeCleanupMemoryService):
    async def create_plan_milestone(self, payload):
        raise RuntimeError("milestone write rejected")

    async def update_plan_milestone(self, milestone_id, **updates):
        raise RuntimeError("milestone write rejected")


def test_build_cleanup_operations_targets_current_mess_without_writes():
    memory = _messy_memory()

    operations = build_cleanup_operations(
        plans=memory.plans,
        milestones=memory.milestones,
        commitments=memory.commitments,
        entities=memory.entities,
    )

    plan_updates = [
        operation
        for operation in operations
        if operation.action == "update_plan"
    ]
    assert {operation.updates["title"] for operation in plan_updates} == {
        RELOCATION_PLAN_TITLE,
        APP_PLAN_TITLE,
        MELISSA_PLAN_TITLE,
    }
    archived_milestones = [
        operation
        for operation in operations
        if operation.action == "archive_plan_milestone"
    ]
    assert {
        operation.record_id
        for operation in archived_milestones
    } >= {
        "milestone-melissa-1",
        "milestone-melissa-2",
        "milestone-first-million",
    }
    assert any(
        operation.record_type == "entity"
        and operation.title == "Stephanie"
        and "not fired" in operation.updates["summary"]
        for operation in operations
    )
    assert any(
        operation.record_type == "commitment"
        and operation.reason == "archive duplicate open commitment"
        for operation in operations
    )


@pytest.mark.asyncio
async def test_cleanup_dry_run_does_not_mutate_records():
    memory = _messy_memory()

    report = await cleanup_rex_brain_v2_current_data(memory, apply=False)

    assert report.dry_run is True
    assert report.applied == []
    assert memory.plans[0]["title"] == "Relocate to Greece"
    assert report.verification["passed"] is False
    assert "active_relocation_plan_still_uses_greece_as_primary" in (
        report.verification["failures"]
    )


@pytest.mark.asyncio
async def test_cleanup_apply_updates_canonical_records_and_verifies():
    memory = _messy_memory()

    report = await cleanup_rex_brain_v2_current_data(memory, apply=True)

    assert report.dry_run is False
    assert all(item["success"] for item in report.applied)
    assert report.verification["passed"] is True
    assert memory.plans[0]["title"] == RELOCATION_PLAN_TITLE
    assert memory.plans[1]["title"] == APP_PLAN_TITLE
    assert memory.plans[2]["title"] == MELISSA_PLAN_TITLE
    assert next(
        entity for entity in memory.entities if entity["display_name"] == "Stephanie"
    )["summary"] == (
        "Lara's friend who lives with her; quit about a month ago. "
        "Stephanie was not fired at the beginning of this year."
    )
    assert all(
        milestone["active"] is False
        for milestone in memory.milestones
        if milestone["id"] in {"milestone-melissa-1", "milestone-melissa-2"}
    )
    assert any(
        milestone["title"] == "Clarity launched"
        and milestone["milestone_type"] == "checkpoint"
        and milestone["metadata"]["achievement_milestone"] is True
        for milestone in memory.milestones
    )
    duplicate_savings = [
        commitment
        for commitment in memory.commitments
        if commitment["id"] in {"commitment-savings-1", "commitment-savings-2"}
    ]
    assert sum(1 for commitment in duplicate_savings if commitment["active"]) == 1


@pytest.mark.asyncio
async def test_cleanup_archives_milestones_from_inactive_parent_plans():
    memory = _messy_memory()
    memory.plans.append(
        _plan(
            "plan-archived-app",
            "Old app launch plan",
            "career",
            description="Archived duplicate app plan.",
            priority=3,
            active=False,
            status="archived",
        )
    )
    memory.milestones.append(
        _milestone(
            "milestone-orphan-app",
            "plan-archived-app",
            "Launch Rex Melissa",
        )
    )

    report = await cleanup_rex_brain_v2_current_data(memory, apply=True)

    assert report.verification["passed"] is True
    orphan = next(
        milestone
        for milestone in memory.milestones
        if milestone["id"] == "milestone-orphan-app"
    )
    assert orphan["active"] is False
    assert orphan["metadata"]["cleanup_reason"] == "orphaned_milestone"


@pytest.mark.asyncio
async def test_cleanup_recreates_app_plan_when_only_app_milestones_remain():
    memory = _messy_memory()
    memory.plans = [plan for plan in memory.plans if plan["id"] != "plan-apps"]

    report = await cleanup_rex_brain_v2_current_data(memory, apply=True)

    assert report.verification["passed"] is True
    assert any(plan["title"] == APP_PLAN_TITLE for plan in memory.plans)


@pytest.mark.asyncio
async def test_cleanup_verification_fails_when_canonical_milestone_writes_fail():
    memory = FailingMilestoneCleanupMemoryService()
    seed = _messy_memory()
    memory.plans = seed.plans
    memory.milestones = seed.milestones
    memory.commitments = seed.commitments
    memory.entities = seed.entities

    report = await cleanup_rex_brain_v2_current_data(memory, apply=True)

    assert report.verification["passed"] is False
    assert "cleanup_operations_failed" in report.verification["failures"]
    assert "canonical_relocation_milestones_missing" in report.verification["failures"]
    assert "canonical_app_milestones_missing" in report.verification["failures"]
    failed = report.verification["remaining_noisy_record_ids"]["failed_operations"]
    assert any(item["record_type"] == "milestone" for item in failed)


def test_verify_cleanup_state_requires_canonical_milestones():
    memory = _messy_memory()
    memory.plans[0]["title"] = RELOCATION_PLAN_TITLE
    memory.plans[0]["description"] = "Italy first, Portugal backup."
    memory.plans[1]["title"] = APP_PLAN_TITLE
    memory.plans[2]["title"] = MELISSA_PLAN_TITLE
    memory.milestones = []

    verification = verify_cleanup_state(
        plans=memory.plans[:3],
        milestones=memory.milestones,
        commitments=[],
        entities=[
            _entity(
                "entity-stephanie",
                "Stephanie",
                "Lara's friend who lives with her; quit about a month ago.",
            )
        ],
    )

    assert verification["passed"] is False
    assert "canonical_relocation_milestones_missing" in verification["failures"]
    assert "canonical_app_milestones_missing" in verification["failures"]


def _messy_memory():
    memory = FakeCleanupMemoryService()
    memory.plans = [
        _plan(
            "plan-relocation",
            "Relocate to Greece",
            "immigration",
            description="Move to Greece for extended stay, supported by app revenue.",
            priority=5,
        ),
        _plan(
            "plan-apps",
            "Three-month app development plan",
            "career",
            description="Prioritize building EchoDesk, FlowForce, and Rex.",
            priority=5,
        ),
        _plan(
            "plan-melissa",
            "Ask Melissa out for dinner",
            "dating",
            description="I invited Melissa today in a teasing way.",
            priority=4,
        ),
        _plan(
            "plan-old-rex",
            "Launch Rex Melissa",
            "personal",
            description="Polish Rex for first usable version.",
            priority=5,
        ),
    ]
    memory.milestones = [
        _milestone(
            "milestone-europe",
            "plan-relocation",
            "Relocate to Europe next year",
        ),
        _milestone(
            "milestone-first-million",
            "plan-relocation",
            "Reach first million",
        ),
        _milestone(
            "milestone-app-noise",
            "plan-apps",
            "Rex AI Assistant Development",
        ),
        _milestone(
            "milestone-melissa-1",
            "plan-melissa",
            "Date with Melissa next week",
        ),
        _milestone(
            "milestone-melissa-2",
            "plan-melissa",
            "Next-week dinner with Melissa",
        ),
    ]
    memory.entities = [
        _entity(
            "entity-lara",
            "Lara",
            "Kitchen supervisor.",
        ),
        _entity(
            "entity-stephanie",
            "Stephanie",
            "Laura's friend who got fired at the beginning of this year.",
        ),
    ]
    memory.commitments = [
        _commitment(
            "commitment-savings-1",
            "Automatic savings",
            "Use automatic savings to build buffer for lawyer fees and move",
        ),
        _commitment(
            "commitment-savings-2",
            "Initial Savings Transfer",
            "Transferred $350 to savings account this month as first step",
        ),
        _commitment(
            "commitment-shipping",
            "Weekly shipping habit",
            "Maintain weekly shipping habit to support income goals",
        ),
    ]
    return memory


def _filtered(rows, **kwargs):
    filtered = list(rows)
    active = kwargs.get("active")
    status = kwargs.get("status")
    limit = kwargs.get("limit", len(filtered))
    if active is not None:
        filtered = [row for row in filtered if row.get("active", True) is active]
    if status is not None:
        filtered = [row for row in filtered if row.get("status") == status]
    return filtered[:limit]


def _update(rows, record_id, updates):
    for row in rows:
        if row["id"] == record_id:
            row.update(updates)
            return row
    return None


def _plan(
    plan_id,
    title,
    plan_type,
    *,
    description,
    priority,
    active=True,
    status="active",
):
    return {
        "id": plan_id,
        "title": title,
        "plan_type": plan_type,
        "description": description,
        "desired_outcome": "",
        "priority": priority,
        "status": status,
        "active": active,
        "metadata": {},
    }


def _milestone(milestone_id, plan_id, title):
    return {
        "id": milestone_id,
        "plan_id": plan_id,
        "title": title,
        "description": "",
        "milestone_type": "goal",
        "priority": 4,
        "status": "open",
        "active": True,
        "metadata": {},
    }


def _commitment(commitment_id, title, commitment_text):
    return {
        "id": commitment_id,
        "title": title,
        "commitment_text": commitment_text,
        "priority": 4,
        "status": "open",
        "active": True,
        "metadata": {},
    }


def _entity(entity_id, display_name, summary):
    return {
        "id": entity_id,
        "display_name": display_name,
        "normalized_name": display_name.casefold(),
        "aliases": [],
        "relationship": "",
        "summary": summary,
        "status": "active",
        "active": True,
        "metadata": {},
    }
