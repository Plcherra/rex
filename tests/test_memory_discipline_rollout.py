import pytest

from scripts.apply_memory_discipline import run_audit


class FakeRolloutMemoryService:
    def __init__(self):
        self.rules = [
            {
                "id": "rule-1",
                "title": "Auto-save $350 per paycheck",
                "rule_text": "Automatically move $350 from each paycheck to savings.",
                "priority": 4,
                "active": True,
                "status": "active",
            },
            {
                "id": "rule-2",
                "title": "Paycheck savings transfer",
                "rule_text": "Transfer at least $350 from each paycheck to savings.",
                "priority": 4,
                "active": True,
                "status": "active",
            },
        ]

    async def list_plans(self, **kwargs):
        return [
            {
                "id": "plan-1",
                "title": "Relocate to Europe next year",
                "description": "Build remote income.",
                "active": True,
            },
            {
                "id": "plan-2",
                "title": "Relocate to Europe next year",
                "description": "Build remote income.",
                "active": True,
            },
        ]

    async def list_personal_rules(self, **kwargs):
        return self.rules

    async def deactivate_personal_rule(self, rule_id):
        for rule in self.rules:
            if rule["id"] == rule_id:
                rule["active"] = False
                rule["status"] = "archived"
                return True
        return False

    async def list_entities(self, **kwargs):
        return []

    async def list_plan_milestones(self, **kwargs):
        return [{"id": "milestone-1", "plan_id": "plan-1"}]

    async def list_commitments(self, **kwargs):
        return [{"id": "commitment-1", "plan_id": "plan-1"}]


@pytest.mark.asyncio
async def test_rollout_audit_reports_counts_and_duplicate_clusters():
    report = await run_audit(FakeRolloutMemoryService(), limit=100)

    assert report["dry_run"] is True
    assert report["applied"] is False
    assert report["records_scanned"] == {
            "plans": 2,
            "rules": 2,
            "entities": 0,
            "milestones": 1,
            "commitments": 1,
    }
    assert report["duplicate_clusters"] == [
        {
            "record_type": "plan",
            "record_ids": ["plan-1", "plan-2"],
            "titles": [
                "Relocate to Europe next year",
                "Relocate to Europe next year",
            ],
        },
        {
            "record_type": "rule",
            "record_ids": ["rule-1", "rule-2"],
            "titles": [
                "Auto-save $350 per paycheck",
                "Paycheck savings transfer",
            ],
        }
    ]
    assert report["updates"] == []
    assert report["archives"] == []


@pytest.mark.asyncio
async def test_rollout_apply_archives_duplicate_rules():
    memory = FakeRolloutMemoryService()

    report = await run_audit(memory, limit=100, apply=True)

    assert report["dry_run"] is False
    assert report["applied"] is True
    assert report["archives"] == [
        {
            "record_type": "rule",
            "id": "rule-2",
            "title": "Paycheck savings transfer",
            "consolidated_into_id": "rule-1",
            "consolidated_into_title": "Auto-save $350 per paycheck",
        }
    ]
    assert memory.rules[1]["active"] is False
