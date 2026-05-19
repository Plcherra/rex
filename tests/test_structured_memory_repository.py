import pytest

from app.config import Settings
from app.services.memory_service import MemoryServiceError, SupabaseMemoryService


class FakeStructuredMemoryService(SupabaseMemoryService):
    def __init__(self):
        self.settings = Settings(_env_file=None)
        self.requests = []
        self.empty_patch_response = False

    async def _request(self, method, table, body=None, query=None, prefer=None):
        self.requests.append(
            {
                "method": method,
                "table": table,
                "body": body,
                "query": query,
                "prefer": prefer,
            }
        )
        if method == "PATCH" and self.empty_patch_response:
            return []
        return [{"id": "record-1", **(body or {})}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "table", "body"),
    [
        (
            "create_memory_correction",
            "memory_corrections",
            {
                "correction_type": "entity_name",
                "old_value": "Al",
                "new_value": "Melissa",
                "target_table": "long_term_memory",
                "target_id": "memory-1",
                "source_conversation_id": None,
                "source_message_id": None,
                "applied": True,
                "confidence": 0.9,
                "metadata": {},
            },
        ),
        (
            "create_entity",
            "entities",
            {
                "entity_type": "person",
                "display_name": "Clara",
                "normalized_name": "clara",
            },
        ),
        (
            "create_entity_event",
            "entity_events",
            {
                "entity_id": "entity-1",
                "event_type": "interaction",
                "content": "Met Clara after work.",
            },
        ),
        (
            "create_personal_rule",
            "personal_rules",
            {
                "rule_type": "transport",
                "title": "No Uber",
                "rule_text": "Do not use Uber unless it is urgent.",
            },
        ),
        (
            "create_plan",
            "plans",
            {
                "plan_type": "immigration",
                "title": "Move country plan",
            },
        ),
        (
            "create_plan_milestone",
            "plan_milestones",
            {
                "plan_id": "plan-1",
                "title": "Submit paperwork",
                "milestone_type": "deadline",
            },
        ),
        (
            "create_commitment",
            "commitments",
            {
                "commitment_type": "health",
                "title": "Morning workout",
                "commitment_text": "Work out tomorrow morning.",
            },
        ),
    ],
)
async def test_structured_memory_create_methods_use_supabase_insert_shape(
    method_name,
    table,
    body,
):
    service = FakeStructuredMemoryService()

    result = await getattr(service, method_name)(body)

    assert result["id"] == "record-1"
    request = service.requests[0]
    assert request["method"] == "POST"
    assert request["table"] == table
    assert request["body"] == body
    assert request["query"]["select"]
    assert request["prefer"] == "return=representation"


@pytest.mark.asyncio
async def test_structured_memory_list_methods_apply_filters_and_ordering():
    service = FakeStructuredMemoryService()

    await service.list_entities(
        limit=10,
        entity_type="person",
        status="active",
        active=True,
        normalized_name="clara",
    )
    await service.list_personal_rules(rule_type="finance", active=True)
    await service.list_plans(plan_type="immigration", status="active")
    await service.list_plan_milestones(plan_id="plan-1", status="open")
    await service.list_commitments(plan_id="plan-1", entity_id="entity-1")
    await service.list_memory_corrections(
        correction_type="entity_name",
        applied=True,
        target_table="long_term_memory",
        target_id="memory-1",
    )

    entity_request = service.requests[0]
    assert entity_request["method"] == "GET"
    assert entity_request["table"] == "entities"
    assert entity_request["query"]["entity_type"] == "eq.person"
    assert entity_request["query"]["status"] == "eq.active"
    assert entity_request["query"]["active"] == "eq.true"
    assert entity_request["query"]["normalized_name"] == "eq.clara"
    assert entity_request["query"]["limit"] == "10"

    assert service.requests[1]["table"] == "personal_rules"
    assert service.requests[1]["query"]["rule_type"] == "eq.finance"
    assert service.requests[2]["table"] == "plans"
    assert service.requests[2]["query"]["plan_type"] == "eq.immigration"
    assert service.requests[3]["table"] == "plan_milestones"
    assert service.requests[3]["query"]["plan_id"] == "eq.plan-1"
    assert service.requests[4]["table"] == "commitments"
    assert service.requests[4]["query"]["entity_id"] == "eq.entity-1"
    assert service.requests[5]["table"] == "memory_corrections"
    assert service.requests[5]["query"]["correction_type"] == "eq.entity_name"
    assert service.requests[5]["query"]["applied"] == "eq.true"
    assert service.requests[5]["query"]["target_table"] == "eq.long_term_memory"
    assert service.requests[5]["query"]["target_id"] == "eq.memory-1"
    assert all(request["query"]["order"] for request in service.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "record_id", "table", "updates"),
    [
        ("update_entity", "entity-1", "entities", {"summary": "Close friend"}),
        (
            "update_entity_event",
            "event-1",
            "entity_events",
            {"content": "Updated event"},
        ),
        (
            "update_personal_rule",
            "rule-1",
            "personal_rules",
            {"priority": 5},
        ),
        ("update_plan", "plan-1", "plans", {"status": "paused"}),
        (
            "update_plan_milestone",
            "milestone-1",
            "plan_milestones",
            {"status": "completed"},
        ),
        (
            "update_commitment",
            "commitment-1",
            "commitments",
            {"status": "missed"},
        ),
    ],
)
async def test_structured_memory_update_methods_use_patch_shape(
    method_name,
    record_id,
    table,
    updates,
):
    service = FakeStructuredMemoryService()

    result = await getattr(service, method_name)(record_id, **updates)

    assert result["id"] == "record-1"
    request = service.requests[0]
    assert request["method"] == "PATCH"
    assert request["table"] == table
    assert request["body"] == updates
    assert request["query"]["id"] == f"eq.{record_id}"
    assert request["query"]["select"]
    assert request["prefer"] == "return=representation"


@pytest.mark.asyncio
async def test_structured_memory_update_rejects_empty_updates():
    service = FakeStructuredMemoryService()

    with pytest.raises(MemoryServiceError) as error:
        await service.update_plan("plan-1")

    assert error.value.status_code == 400
    assert "At least one plan field" in error.value.detail
    assert service.requests == []


@pytest.mark.asyncio
async def test_structured_memory_deactivate_methods_update_active_and_status():
    service = FakeStructuredMemoryService()

    assert await service.deactivate_entity("entity-1") is True
    assert await service.deactivate_personal_rule("rule-1") is True
    assert await service.deactivate_plan("plan-1") is True
    assert await service.deactivate_plan_milestone("milestone-1") is True
    assert await service.deactivate_commitment("commitment-1") is True
    assert await service.deactivate_entity_event("event-1") is True

    assert service.requests[0]["body"] == {"active": False, "status": "inactive"}
    assert service.requests[1]["body"] == {"active": False, "status": "archived"}
    assert service.requests[2]["body"] == {"active": False, "status": "archived"}
    assert service.requests[3]["body"] == {"active": False, "status": "canceled"}
    assert service.requests[4]["body"] == {"active": False, "status": "archived"}
    assert service.requests[5]["body"] == {"active": False}


@pytest.mark.asyncio
async def test_structured_memory_deactivate_returns_false_when_row_missing():
    service = FakeStructuredMemoryService()
    service.empty_patch_response = True

    assert await service.deactivate_commitment("missing") is False
