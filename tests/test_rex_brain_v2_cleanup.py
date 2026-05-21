import pytest

from backend.scripts.cleanup_rex_brain_v2_current_data import (
    APP_PLAN_TITLE,
    MELISSA_PLAN_TITLE,
    RELOCATION_PLAN_TITLE,
    build_cleanup_operations,
    cleanup_rex_brain_v2_current_data,
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
        and milestone["milestone_type"] == "achievement"
        for milestone in memory.milestones
    )


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


def _plan(plan_id, title, plan_type, *, description, priority):
    return {
        "id": plan_id,
        "title": title,
        "plan_type": plan_type,
        "description": description,
        "desired_outcome": "",
        "priority": priority,
        "status": "active",
        "active": True,
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
