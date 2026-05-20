import pytest

from scripts.apply_memory_discipline import run_audit


class FakeRolloutMemoryService:
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
        return [
            {
                "id": "rule-1",
                "title": "No DoorDash",
                "rule_text": "Avoid DoorDash.",
            }
        ]

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
        "rules": 1,
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
        }
    ]
    assert report["updates"] == []
    assert report["archives"] == []
