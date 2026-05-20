import pytest

from backend.scripts.backfill_structured_memory import (
    backfill_structured_memory,
    build_backfill_candidates,
)


class FakeBackfillMemoryService:
    def __init__(self, memories):
        self.memories = memories
        self.entities = []
        self.plans = []
        self.rules = []
        self.entity_updates = []
        self.plan_updates = []
        self.rule_updates = []

    async def list_long_term_memory(self, limit=100, active=True):
        return self.memories[:limit]

    async def list_entities(
        self,
        limit=50,
        entity_type=None,
        status=None,
        active=None,
        normalized_name=None,
    ):
        rows = self.entities
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if normalized_name is not None:
            rows = [
                row for row in rows if row.get("normalized_name") == normalized_name
            ]
        if active is not None:
            rows = [row for row in rows if row.get("active", True) is active]
        return rows[:limit]

    async def create_entity(self, payload):
        row = {
            "id": f"entity-{len(self.entities) + 1}",
            "active": True,
            "status": "active",
            "aliases": [],
            **payload,
        }
        self.entities.append(row)
        return row

    async def update_entity(self, entity_id, **updates):
        self.entity_updates.append((entity_id, updates))
        for entity in self.entities:
            if entity["id"] == entity_id:
                entity.update(updates)
                return entity
        return None

    async def list_plans(self, limit=50, plan_type=None, status=None, active=None):
        rows = self.plans
        if plan_type is not None:
            rows = [row for row in rows if row.get("plan_type") == plan_type]
        if active is not None:
            rows = [row for row in rows if row.get("active", True) is active]
        return rows[:limit]

    async def create_plan(self, payload):
        row = {
            "id": f"plan-{len(self.plans) + 1}",
            "active": True,
            "status": "active",
            **payload,
        }
        self.plans.append(row)
        return row

    async def update_plan(self, plan_id, **updates):
        self.plan_updates.append((plan_id, updates))
        for plan in self.plans:
            if plan["id"] == plan_id:
                plan.update(updates)
                return plan
        return None

    async def list_personal_rules(
        self,
        limit=50,
        rule_type=None,
        status=None,
        active=None,
    ):
        rows = self.rules
        if rule_type is not None:
            rows = [row for row in rows if row.get("rule_type") == rule_type]
        if active is not None:
            rows = [row for row in rows if row.get("active", True) is active]
        return rows[:limit]

    async def create_personal_rule(self, payload):
        row = {
            "id": f"rule-{len(self.rules) + 1}",
            "active": True,
            "status": "active",
            "trigger_keywords": [],
            **payload,
        }
        self.rules.append(row)
        return row

    async def update_personal_rule(self, rule_id, **updates):
        self.rule_updates.append((rule_id, updates))
        for rule in self.rules:
            if rule["id"] == rule_id:
                rule.update(updates)
                return rule
        return None


def test_build_backfill_candidates_extracts_location_and_skips_ambiguous_names():
    location_candidates = build_backfill_candidates(
        {
            "id": "memory-1",
            "memory_type": "fact",
            "content": "I am in Massachusetts.",
            "importance": 3,
        }
    )
    ambiguous_candidates = build_backfill_candidates(
        {
            "id": "memory-2",
            "memory_type": "event",
            "content": "I am planning to ask Al out for dinner on Monday.",
            "importance": 3,
        }
    )

    assert location_candidates[0].kind == "entity"
    assert location_candidates[0].payload["entity_type"] == "place"
    assert location_candidates[0].payload["display_name"] == "Massachusetts"
    assert ambiguous_candidates == []


def test_build_backfill_candidates_extracts_corrected_person_and_linked_plan():
    candidates = build_backfill_candidates(
        {
            "id": "memory-3",
            "memory_type": "fact",
            "content": "The person for the next-week date plan is Melissa, corrected from Al or AI.",
            "importance": 4,
        }
    )

    assert [candidate.kind for candidate in candidates] == ["entity", "plan"]
    assert candidates[0].payload["display_name"] == "Melissa"
    assert candidates[0].payload["aliases"] == []
    assert candidates[0].payload["metadata"]["wrong_names"] == ["ai", "al"]
    assert candidates[1].payload["metadata"]["wrong_names"] == ["ai", "al"]
    assert candidates[1].payload["title"] == "Ask Melissa out for dinner"
    assert candidates[0].link_key == candidates[1].link_key


@pytest.mark.asyncio
async def test_backfill_structured_memory_dry_run_does_not_write():
    service = FakeBackfillMemoryService(
        [
            {
                "id": "memory-1",
                "memory_type": "fact",
                "content": "I am in Massachusetts.",
                "importance": 3,
            }
        ]
    )

    report = await backfill_structured_memory(service, apply=False)

    assert report.scanned == 1
    assert len(report.candidates) == 1
    assert report.upserted == []
    assert service.entities == []


@pytest.mark.asyncio
async def test_backfill_structured_memory_links_person_to_plan_when_applied():
    service = FakeBackfillMemoryService(
        [
            {
                "id": "memory-3",
                "memory_type": "fact",
                "content": "The person for the next-week date plan is Melissa, corrected from Al or AI.",
                "importance": 4,
            }
        ]
    )

    report = await backfill_structured_memory(service, apply=True)

    assert report.errors == []
    assert len(service.entities) == 1
    assert len(service.plans) == 1
    assert service.entities[0]["display_name"] == "Melissa"
    assert service.plans[0]["primary_entity_id"] == service.entities[0]["id"]
    assert service.plans[0]["metadata"]["backfilled_from"] == "long_term_memory"
    assert [row["kind"] for row in report.upserted] == ["entity", "plan"]


@pytest.mark.asyncio
async def test_backfill_structured_memory_uses_services_to_merge_duplicates():
    service = FakeBackfillMemoryService(
        [
            {
                "id": "memory-1",
                "memory_type": "fact",
                "content": "I am in Massachusetts.",
                "importance": 3,
            }
        ]
    )
    service.entities.append(
        {
            "id": "entity-existing",
            "entity_type": "place",
            "display_name": "Massachusetts",
            "normalized_name": "massachusetts",
            "importance": 2,
            "active": True,
            "aliases": [],
            "metadata": {},
        }
    )

    report = await backfill_structured_memory(service, apply=True)

    assert len(service.entities) == 1
    assert service.entity_updates[0][0] == "entity-existing"
    assert service.entity_updates[0][1]["source_memory_id"] == "memory-1"
    assert report.upserted[0]["id"] == "entity-existing"


@pytest.mark.asyncio
async def test_backfill_archives_stale_wrong_name_records_from_existing_correction():
    service = FakeBackfillMemoryService(
        [
            {
                "id": "memory-5",
                "memory_type": "event",
                "content": "I invited Melissa today in a teasing way, with a next-week dinner planned.",
                "source_conversation_id": "conversation-1",
                "source_message_id": "message-1",
                "importance": 4,
            }
        ]
    )
    service.entities.extend(
        [
            {
                "id": "entity-melissa",
                "entity_type": "person",
                "display_name": "Melissa",
                "normalized_name": "melissa",
                "aliases": ["Al", "AI", "coworker"],
                "relationship": "person in next-week date plan",
                "summary": (
                    "Corrected name for the date plan participant "
                    "(previously referenced as Al or AI)"
                ),
                "importance": 4,
                "active": True,
                "status": "active",
                "metadata": {},
            },
            {
                "id": "entity-al",
                "entity_type": "person",
                "display_name": "Al",
                "normalized_name": "al",
                "aliases": ["AI"],
                "relationship": "person the user is planning to ask out on a date",
                "summary": "Al has an off-day on Monday.",
                "importance": 4,
                "active": True,
                "status": "active",
                "metadata": {},
            },
            {
                "id": "entity-next-week-date",
                "entity_type": "person",
                "display_name": "next week date",
                "normalized_name": "next week date",
                "aliases": [],
                "relationship": "date the user is planning for next week",
                "summary": "Name is not Al and not AI.",
                "importance": 4,
                "active": True,
                "status": "active",
                "metadata": {},
            },
        ]
    )
    service.plans.extend(
        [
            {
                "id": "plan-melissa",
                "plan_type": "dating",
                "title": "Ask Melissa out for dinner",
                "description": "Dinner with Melissa.",
                "desired_outcome": "Successful date with Melissa.",
                "primary_entity_id": "entity-melissa",
                "priority": 4,
                "status": "active",
                "active": True,
                "metadata": {},
            },
            {
                "id": "plan-al",
                "plan_type": "dating",
                "title": "Ask Al out for dinner",
                "description": "Dinner with Al on Monday.",
                "desired_outcome": "Successful date with Al.",
                "primary_entity_id": None,
                "priority": 4,
                "status": "active",
                "active": True,
                "metadata": {},
            },
        ]
    )

    report = await backfill_structured_memory(service, apply=True)

    assert report.errors == []
    melissa = next(entity for entity in service.entities if entity["id"] == "entity-melissa")
    assert melissa["aliases"] == ["coworker"]
    assert melissa["metadata"]["removed_wrong_aliases"] == ["Al", "AI"]
    stale_al = next(entity for entity in service.entities if entity["id"] == "entity-al")
    stale_generic = next(
        entity for entity in service.entities if entity["id"] == "entity-next-week-date"
    )
    assert stale_al["active"] is False
    assert stale_generic["active"] is False
    stale_plan = next(plan for plan in service.plans if plan["id"] == "plan-al")
    assert stale_plan["active"] is False
    assert stale_plan["status"] == "archived"


@pytest.mark.asyncio
async def test_backfill_structured_memory_extracts_simple_rule():
    service = FakeBackfillMemoryService(
        [
            {
                "id": "memory-4",
                "memory_type": "preference",
                "content": "I should avoid Uber unless it is urgent.",
                "importance": 3,
            }
        ]
    )

    report = await backfill_structured_memory(service, apply=True)

    assert report.errors == []
    assert service.rules[0]["rule_type"] == "transport"
    assert service.rules[0]["trigger_keywords"] == ["uber", "lyft", "taxi"]
