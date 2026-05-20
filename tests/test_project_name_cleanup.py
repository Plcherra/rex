import pytest

from backend.scripts.cleanup_project_names import cleanup_project_names


class FakeProjectNameMemoryService:
    def __init__(self):
        self.entities = []
        self.memories = []
        self.plans = []
        self.milestones = []
        self.rules = []
        self.commitments = []

    async def list_entities(
        self,
        limit=500,
        entity_type=None,
        status=None,
        active=None,
        normalized_name=None,
    ):
        rows = self.entities
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active", True) is active]
        if normalized_name is not None:
            rows = [row for row in rows if row.get("normalized_name") == normalized_name]
        return rows[:limit]

    async def create_entity(self, payload):
        row = {"id": f"entity-{len(self.entities) + 1}", **payload}
        self.entities.append(row)
        return row

    async def update_entity(self, entity_id, **updates):
        return _update(self.entities, entity_id, updates)

    async def list_long_term_memory(self, limit=500, memory_type=None, active=None):
        return _list(self.memories, limit, active)

    async def update_long_term_memory(self, memory_id, **updates):
        return _update(self.memories, memory_id, updates)

    async def list_plans(self, limit=500, plan_type=None, status=None, active=None):
        return _list(self.plans, limit, active)

    async def update_plan(self, plan_id, **updates):
        return _update(self.plans, plan_id, updates)

    async def list_plan_milestones(
        self,
        limit=500,
        plan_id=None,
        status=None,
        active=None,
    ):
        return _list(self.milestones, limit, active)

    async def update_plan_milestone(self, milestone_id, **updates):
        return _update(self.milestones, milestone_id, updates)

    async def list_personal_rules(
        self,
        limit=500,
        rule_type=None,
        status=None,
        active=None,
    ):
        return _list(self.rules, limit, active)

    async def update_personal_rule(self, rule_id, **updates):
        return _update(self.rules, rule_id, updates)

    async def list_commitments(
        self,
        limit=500,
        commitment_type=None,
        plan_id=None,
        entity_id=None,
        status=None,
        active=None,
    ):
        return _list(self.commitments, limit, active)

    async def update_commitment(self, commitment_id, **updates):
        return _update(self.commitments, commitment_id, updates)


def _list(rows, limit, active):
    if active is not None:
        rows = [row for row in rows if row.get("active", True) is active]
    return rows[:limit]


def _update(rows, row_id, updates):
    for row in rows:
        if row["id"] == row_id:
            row.update(updates)
            return row
    return None


@pytest.mark.asyncio
async def test_cleanup_project_names_dry_run_does_not_write():
    memory = FakeProjectNameMemoryService()
    memory.plans.append(
        {
            "id": "plan-1",
            "title": "Three-month app development plan",
            "description": "Prioritize Flowfirst and Echotask.",
            "active": True,
        }
    )
    memory.entities.append(
        {
            "id": "entity-flow",
            "entity_type": "project",
            "display_name": "Flow",
            "normalized_name": "flow",
            "active": True,
            "status": "active",
            "metadata": {},
        }
    )

    report = await cleanup_project_names(memory, apply=False)

    assert report.updated[0]["table"] == "plans"
    assert report.archived_entities[0]["corrected_to"] == "FlowForce"
    assert memory.plans[0]["description"] == "Prioritize Flowfirst and Echotask."
    assert memory.entities[0]["active"] is True


@pytest.mark.asyncio
async def test_cleanup_project_names_updates_text_and_archives_stale_entities():
    memory = FakeProjectNameMemoryService()
    memory.entities.extend(
        [
            {
                "id": "entity-flow",
                "entity_type": "project",
                "display_name": "Flowfirst",
                "normalized_name": "flowfirst",
                "active": True,
                "status": "active",
                "metadata": {},
            },
            {
                "id": "entity-flowforce",
                "entity_type": "project",
                "display_name": "Flowforce",
                "normalized_name": "flowforce",
                "aliases": ["echotask"],
                "active": True,
                "status": "active",
                "metadata": {"source_content": "old Echotask mention"},
            },
            {
                "id": "entity-combined",
                "entity_type": "project",
                "display_name": "Flow + Echotask",
                "normalized_name": "flow echotask",
                "active": True,
                "status": "active",
                "metadata": {},
            },
        ]
    )
    memory.plans.append(
        {
            "id": "plan-1",
            "title": "Three-month app development plan",
            "description": "Prioritize Flow, Echotask, and Flowforte.",
            "desired_outcome": "Ship Flowfirst MVP.",
            "metadata": {"source_content": "Flow + Echotask"},
            "active": True,
        }
    )
    memory.milestones.append(
        {
            "id": "milestone-1",
            "title": "Flowfirst client acquisition",
            "description": "Sell Flow + Echotask.",
            "metadata": {},
            "active": True,
        }
    )

    report = await cleanup_project_names(memory, apply=True)

    assert report.errors == []
    assert memory.entities[0]["active"] is False
    assert memory.entities[0]["status"] == "inactive"
    assert memory.entities[0]["metadata"]["corrected_to"] == "FlowForce"
    assert memory.entities[1]["aliases"] == []
    assert memory.entities[1]["display_name"] == "FlowForce"
    assert memory.entities[1]["normalized_name"] == "flowforce"
    assert memory.entities[1]["metadata"]["source_content"] == "old EchoDesk mention"
    assert memory.entities[2]["active"] is False
    assert memory.entities[2]["metadata"]["corrected_to"] == "EchoDesk and FlowForce"
    assert memory.plans[0]["description"] == (
        "Prioritize EchoDesk, FlowForce."
    )
    assert memory.plans[0]["desired_outcome"] == "Ship FlowForce MVP."
    assert memory.plans[0]["metadata"]["source_content"] == "FlowForce + EchoDesk"
    assert memory.milestones[0]["title"] == "FlowForce client acquisition"
    assert memory.milestones[0]["description"] == "Sell FlowForce + EchoDesk."
