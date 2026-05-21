import pytest

from app.services.memory_correction_service import (
    CorrectionIntentType,
    MemoryCorrectionService,
)


class FakeMemoryCorrectionRepository:
    def __init__(self):
        self.memories = []
        self.entities = []
        self.entity_events = []
        self.rules = []
        self.plans = []
        self.milestones = []
        self.commitments = []
        self.corrections = []

    async def list_long_term_memory(self, limit=50, memory_type=None, active=None):
        return _filter_active(self.memories, active)[:limit]

    async def list_entities(
        self,
        limit=50,
        entity_type=None,
        status=None,
        active=None,
        normalized_name=None,
    ):
        return _filter_active(self.entities, active)[:limit]

    async def list_entity_events(
        self,
        limit=50,
        entity_id=None,
        event_type=None,
        active=None,
    ):
        return _filter_active(self.entity_events, active)[:limit]

    async def list_personal_rules(
        self,
        limit=50,
        rule_type=None,
        status=None,
        active=None,
    ):
        return _filter_active(self.rules, active)[:limit]

    async def list_plans(self, limit=50, plan_type=None, status=None, active=None):
        return _filter_active(self.plans, active)[:limit]

    async def list_plan_milestones(
        self,
        limit=50,
        plan_id=None,
        status=None,
        active=None,
    ):
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
        return _filter_active(self.commitments, active)[:limit]

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


def test_detect_correction_intent_classifies_common_phrases():
    service = MemoryCorrectionService(FakeMemoryCorrectionRepository())

    name = service.detect_correction_intent("not Flowfirst, it is FlowForce")
    removal = service.detect_correction_intent("delete any mention of Echotask")
    merge = service.detect_correction_intent("merge these plans")
    move = service.detect_correction_intent("that should be under the Europe plan")
    task = service.detect_correction_intent("this is not a plan, it is just a task")

    assert name.intent_type == CorrectionIntentType.REPLACE_VALUE
    assert name.old_value == "Flowfirst"
    assert name.new_value == "FlowForce"
    assert removal.intent_type == CorrectionIntentType.REMOVE_OBSOLETE
    assert removal.old_value == "Echotask"
    assert merge.intent_type == CorrectionIntentType.MERGE_ITEMS
    assert merge.requires_confirmation is True
    assert move.intent_type == CorrectionIntentType.MOVE_UNDER_PARENT
    assert task.intent_type == CorrectionIntentType.DOWNGRADE_PLAN_TO_TASK


@pytest.mark.asyncio
async def test_apply_name_correction_updates_records_and_audits_changes():
    repo = FakeMemoryCorrectionRepository()
    repo.plans.append(
        {
            "id": "plan-1",
            "title": "Launch Flowfirst",
            "description": "Use Flowfirst to get revenue.",
            "desired_outcome": "Revenue from Flowfirst.",
            "active": True,
            "metadata": {},
        }
    )
    repo.commitments.append(
        {
            "id": "commitment-1",
            "title": "Ship Flowfirst MVP",
            "commitment_text": "Finish Flowfirst this month.",
            "active": True,
            "metadata": {},
        }
    )

    report = await MemoryCorrectionService(repo).apply_correction(
        "not Flowfirst, it is FlowForce",
        source_conversation_id="conversation-1",
        source_message_id="message-1",
    )

    assert report.applied is True
    assert repo.plans[0]["title"] == "Launch FlowForce"
    assert repo.commitments[0]["commitment_text"] == "Finish FlowForce this month."
    assert len(repo.corrections) == 2
    assert repo.corrections[0]["old_value"] == "Flowfirst"
    assert repo.corrections[0]["new_value"] == "FlowForce"
    assert repo.corrections[0]["applied"] is True


@pytest.mark.asyncio
async def test_apply_remove_correction_archives_matching_active_records():
    repo = FakeMemoryCorrectionRepository()
    repo.entities.append(
        {
            "id": "entity-1",
            "display_name": "Echotask",
            "normalized_name": "echotask",
            "summary": "Wrong project name",
            "active": True,
            "metadata": {},
        }
    )
    repo.memories.append(
        {
            "id": "memory-1",
            "content": "Echotask is one of the user's projects.",
            "active": True,
            "metadata": {},
        }
    )

    report = await MemoryCorrectionService(repo).apply_correction(
        "delete any mention of Echotask"
    )

    assert report.applied is True
    assert repo.entities[0]["active"] is False
    assert repo.memories[0]["active"] is False
    assert len(repo.corrections) == 2
    assert {item["target_table"] for item in repo.corrections} == {
        "entities",
        "long_term_memory",
    }


@pytest.mark.asyncio
async def test_apply_person_fact_correction_updates_lara_and_removes_stephanie_fired_fact():
    repo = FakeMemoryCorrectionRepository()
    repo.entities.extend(
        [
            {
                "id": "entity-lara",
                "display_name": "Lara",
                "normalized_name": "lara",
                "summary": "Kitchen supervisor.",
                "relationship": "kitchen supervisor",
                "active": True,
                "metadata": {},
            },
            {
                "id": "entity-stephanie",
                "display_name": "Stephanie",
                "normalized_name": "stephanie",
                "summary": "got fired at the beginning of this year",
                "relationship": "Laura's friend who lives with her",
                "active": True,
                "metadata": {},
            },
        ]
    )

    report = await MemoryCorrectionService(repo).apply_correction(
        "Lara is the kitchen supervisor who got fired at the beginning of the year. "
        "Stephanie is her friend that lives with her, and Stephanie quit just a month ago. "
        "Stephanie was not fired at the beginning of this year.",
        force=True,
    )

    assert report.applied is True
    assert "got fired" in repo.entities[0]["summary"]
    assert "quit just a month ago" in repo.entities[1]["summary"]
    assert "got fired" not in repo.entities[1]["summary"]
    assert report.as_dict()["verification_stale_terms"] == [
        "Stephanie got fired",
        "Stephanie was fired",
    ]


@pytest.mark.asyncio
async def test_high_impact_correction_requires_confirmation_before_apply():
    repo = FakeMemoryCorrectionRepository()
    for index in range(6):
        repo.plans.append(
            {
                "id": f"plan-{index}",
                "title": f"Flowfirst item {index}",
                "description": "Wrong name",
                "active": True,
                "metadata": {},
            }
        )

    report = await MemoryCorrectionService(repo).apply_correction(
        "not Flowfirst, it is FlowForce"
    )

    assert report.applied is False
    assert report.requires_confirmation is True
    assert report.confirmation_payload["affected_count"] == 6
    assert all("Flowfirst" in plan["title"] for plan in repo.plans)

    forced = await MemoryCorrectionService(repo).apply_correction(
        "not Flowfirst, it is FlowForce",
        force=True,
    )

    assert forced.applied is True
    assert all("FlowForce" in plan["title"] for plan in repo.plans)
