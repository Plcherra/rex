import pytest
from pydantic import ValidationError

from app.models.personal_rule import (
    PersonalRuleCreateRequest,
    PersonalRuleUpdateRequest,
)
from app.services.memory_service import MemoryServiceError
from app.services.rule_service import RuleService, RuleServiceError


class FakeRuleMemoryService:
    def __init__(self, error=None):
        self.error = error
        self.rules = []

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def create_personal_rule(self, payload):
        self._raise_if_configured()
        row = {"id": f"rule-{len(self.rules) + 1}", **payload}
        self.rules.append(row)
        return row

    async def list_personal_rules(
        self,
        rule_type=None,
        status=None,
        active=True,
        limit=50,
    ):
        self._raise_if_configured()
        rows = self.rules
        if rule_type is not None:
            rows = [row for row in rows if row.get("rule_type") == rule_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_personal_rule(self, rule_id, **updates):
        self._raise_if_configured()
        for row in self.rules:
            if row["id"] == rule_id:
                row.update(updates)
                return row
        return None

    async def deactivate_personal_rule(self, rule_id):
        return await self.update_personal_rule(
            rule_id,
            active=False,
            status="archived",
        )


def test_personal_rule_models_reject_invalid_schema_values():
    with pytest.raises(ValidationError):
        PersonalRuleCreateRequest(
            rule_type="random",
            title="No DoorDash",
            rule_text="Avoid delivery.",
        )

    with pytest.raises(ValidationError):
        PersonalRuleCreateRequest(
            rule_type="finance",
            title="No DoorDash",
            rule_text="Avoid delivery.",
            priority=0,
        )

    with pytest.raises(ValidationError):
        PersonalRuleCreateRequest(
            rule_type="finance",
            title="No DoorDash",
            rule_text="Avoid delivery.",
            enforcement_style="loud",
        )


@pytest.mark.asyncio
async def test_rule_create_update_deactivate_and_active_listing_flow():
    memory = FakeRuleMemoryService()
    service = RuleService(memory)

    created = await service.create_rule(
        PersonalRuleCreateRequest(
            rule_type="food_delivery",
            title="  No   DoorDash ",
            rule_text="  Avoid DoorDash while budget is slipping. ",
            trigger_keywords=["DoorDash", "doordash", " Uber Eats "],
            priority=4,
        )
    )

    assert created["title"] == "No DoorDash"
    assert created["rule_text"] == "Avoid DoorDash while budget is slipping."
    assert created["trigger_keywords"] == ["DoorDash", "Uber Eats"]

    active_rules = await service.list_rules(rule_type="food_delivery", status="active")
    assert active_rules == [created]

    updated = await service.update_rule(
        created["id"],
        PersonalRuleUpdateRequest(
            title="No delivery apps",
            trigger_keywords=["DoorDash", "Grubhub"],
            priority=5,
        ),
    )
    assert updated["title"] == "No delivery apps"
    assert updated["trigger_keywords"] == ["DoorDash", "Grubhub"]
    assert updated["priority"] == 5

    deactivated = await service.deactivate_rule(created["id"])
    assert deactivated["active"] is False
    assert deactivated["status"] == "archived"
    assert await service.list_rules(active=True) == []


@pytest.mark.asyncio
async def test_rule_service_deduplicates_by_normalized_rule_text():
    memory = FakeRuleMemoryService()
    memory.rules.append(
        {
            "id": "rule-existing",
            "rule_type": "food_delivery",
            "title": "No DoorDash",
            "rule_text": "No DoorDash this month.",
            "trigger_keywords": ["DoorDash"],
            "priority": 3,
            "status": "active",
            "active": True,
            "metadata": {"source": "manual"},
        }
    )
    service = RuleService(memory)

    row = await service.create_rule(
        PersonalRuleCreateRequest(
            rule_type="food_delivery",
            title="No delivery",
            rule_text=" no   doordash this month. ",
            trigger_keywords=["DoorDash", "Uber Eats"],
            priority=5,
            metadata={"extracted": True},
        )
    )

    assert row["id"] == "rule-existing"
    assert row["trigger_keywords"] == ["DoorDash", "Uber Eats"]
    assert row["priority"] == 5
    assert row["metadata"] == {"source": "manual", "extracted": True}
    assert len(memory.rules) == 1


@pytest.mark.asyncio
async def test_rule_service_failure_paths_do_not_call_supabase():
    service = RuleService(FakeRuleMemoryService())

    with pytest.raises(RuleServiceError) as missing_error:
        await service.update_rule("missing", PersonalRuleUpdateRequest(priority=5))
    assert missing_error.value.status_code == 404

    failing_service = RuleService(
        FakeRuleMemoryService(MemoryServiceError("Cannot reach memory.", 503))
    )
    with pytest.raises(RuleServiceError) as repo_error:
        await failing_service.list_rules()
    assert repo_error.value.detail == "Cannot reach memory."
    assert repo_error.value.status_code == 503
