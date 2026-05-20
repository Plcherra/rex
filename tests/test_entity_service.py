import pytest
from pydantic import ValidationError

from app.models.entity import (
    EntityCreateRequest,
    EntityEventCreateRequest,
    EntityEventUpdateRequest,
    EntityUpdateRequest,
)
from app.services.entity_service import EntityService, EntityServiceError
from app.services.memory_service import MemoryServiceError


class FakeEntityMemoryService:
    def __init__(self, error=None):
        self.error = error
        self.entities = []
        self.entity_events = []

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def create_entity(self, payload):
        self._raise_if_configured()
        row = {"id": f"entity-{len(self.entities) + 1}", **payload}
        self.entities.append(row)
        return row

    async def list_entities(
        self,
        entity_type=None,
        normalized_name=None,
        status=None,
        active=True,
        limit=50,
    ):
        self._raise_if_configured()
        rows = self.entities
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if normalized_name is not None:
            rows = [
                row for row in rows if row.get("normalized_name") == normalized_name
            ]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_entity(self, entity_id, **updates):
        self._raise_if_configured()
        for row in self.entities:
            if row["id"] == entity_id:
                row.update(updates)
                return row
        return None

    async def deactivate_entity(self, entity_id):
        return await self.update_entity(entity_id, active=False, status="inactive")

    async def create_entity_event(self, payload):
        self._raise_if_configured()
        row = {"id": f"event-{len(self.entity_events) + 1}", **payload}
        self.entity_events.append(row)
        return row

    async def list_entity_events(
        self,
        entity_id=None,
        event_type=None,
        active=True,
        limit=50,
    ):
        self._raise_if_configured()
        rows = self.entity_events
        if entity_id is not None:
            rows = [row for row in rows if row.get("entity_id") == entity_id]
        if event_type is not None:
            rows = [row for row in rows if row.get("event_type") == event_type]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_entity_event(self, event_id, **updates):
        self._raise_if_configured()
        for row in self.entity_events:
            if row["id"] == event_id:
                row.update(updates)
                return row
        return None

    async def deactivate_entity_event(self, event_id):
        return await self.update_entity_event(event_id, active=False)


def test_entity_models_reject_invalid_schema_values():
    with pytest.raises(ValidationError):
        EntityCreateRequest(
            entity_type="animal",
            display_name="Clara",
            normalized_name="clara",
        )

    with pytest.raises(ValidationError):
        EntityCreateRequest(
            entity_type="person",
            display_name="Clara",
            normalized_name="clara",
            importance=7,
        )

    with pytest.raises(ValidationError):
        EntityEventCreateRequest(entity_id="entity-1", event_type="random", content="")


@pytest.mark.asyncio
async def test_entity_create_update_deactivate_and_active_listing_flow():
    memory = FakeEntityMemoryService()
    service = EntityService(memory)

    created = await service.create_entity(
        EntityCreateRequest(
            entity_type="person",
            display_name="  the girl Clara  ",
            normalized_name="Clara from work",
            aliases=["Clara", "clara", "  C  "],
            relationship="Dating interest",
        )
    )

    assert created["display_name"] == "Clara"
    assert created["normalized_name"] == "clara"
    assert created["aliases"] == ["C", "the girl Clara", "Clara from work"]

    listed = await service.list_entities(normalized_name=" Clara ")
    assert listed == [created]

    updated = await service.update_entity(
        created["id"],
        EntityUpdateRequest(display_name="Clara Martins", importance=5),
    )
    assert updated["display_name"] == "Clara Martins"
    assert updated["normalized_name"] == "clara martins"
    assert updated["importance"] == 5

    deactivated = await service.deactivate_entity(created["id"])
    assert deactivated["active"] is False
    assert deactivated["status"] == "inactive"
    assert await service.list_entities(active=True) == []


@pytest.mark.asyncio
async def test_entity_service_deduplicates_by_alias_and_descriptive_name():
    memory = FakeEntityMemoryService()
    memory.entities.append(
        {
            "id": "entity-existing",
            "entity_type": "person",
            "display_name": "Clara",
            "normalized_name": "clara",
            "aliases": ["Clara"],
            "importance": 3,
            "active": True,
            "status": "active",
            "metadata": {"source": "manual"},
        }
    )
    service = EntityService(memory)

    row = await service.create_entity(
        EntityCreateRequest(
            entity_type="person",
            display_name="Clara from work",
            normalized_name="the girl Clara",
            aliases=["Clara from work"],
            summary="Clara is part of the current dating story.",
            importance=5,
            metadata={"extracted": True},
        )
    )

    assert row["id"] == "entity-existing"
    assert row["aliases"] == ["Clara", "Clara from work", "the girl Clara"]
    assert row["summary"] == "Clara is part of the current dating story."
    assert row["importance"] == 5
    assert row["metadata"] == {"source": "manual", "extracted": True}
    assert len(memory.entities) == 1


@pytest.mark.asyncio
async def test_entity_service_archives_wrong_person_after_name_correction():
    memory = FakeEntityMemoryService()
    memory.entities.extend(
        [
            {
                "id": "entity-al",
                "entity_type": "person",
                "display_name": "Al",
                "normalized_name": "al",
                "aliases": ["AI"],
                "relationship": "person the user is planning to ask out",
                "summary": "Al has Monday off.",
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
    service = EntityService(memory)

    row = await service.create_entity(
        EntityCreateRequest(
            entity_type="person",
            display_name="Melissa",
            normalized_name="melissa",
            aliases=["Al", "AI"],
            relationship="person in next-week date plan",
            summary="Corrected name for the date plan participant.",
            importance=5,
            metadata={
                "wrong_names": ["Al", "AI"],
                "correction_source": "explicit_person_correction",
            },
        )
    )

    assert row["display_name"] == "Melissa"
    assert row["id"] != "entity-al"
    assert len(memory.entities) == 3
    stale_rows = {
        row["id"]: row for row in memory.entities if row["id"] != "entity-3"
    }
    assert stale_rows["entity-al"]["active"] is False
    assert stale_rows["entity-al"]["status"] == "inactive"
    assert stale_rows["entity-al"]["metadata"]["superseded_by_entity_id"] == (
        "entity-3"
    )
    assert stale_rows["entity-next-week-date"]["active"] is False
    assert stale_rows["entity-next-week-date"]["metadata"][
        "cleanup_reason"
    ] == "explicit_person_correction"


@pytest.mark.asyncio
async def test_entity_service_reuses_canonical_entity_for_obsolete_project_name():
    memory = FakeEntityMemoryService()
    memory.entities.append(
        {
            "id": "entity-echodesk",
            "entity_type": "project",
            "display_name": "EchoDesk",
            "normalized_name": "echodesk",
            "aliases": [],
            "relationship": "active project",
            "summary": "Canonical app name.",
            "importance": 4,
            "active": True,
            "status": "active",
            "metadata": {"obsolete_aliases": ["Echotask"]},
        }
    )
    service = EntityService(memory)

    row = await service.create_entity(
        EntityCreateRequest(
            entity_type="project",
            display_name="Echotask",
            normalized_name="echotask",
            aliases=["Echotask"],
            summary="Misstated project name.",
            importance=5,
        )
    )

    assert row["id"] == "entity-echodesk"
    assert row["display_name"] == "EchoDesk"
    assert row["aliases"] == []
    assert row["importance"] == 5
    assert row["metadata"]["canonical_entity_id"] == "entity-echodesk"
    assert row["metadata"]["obsolete_aliases"] == ["echotask"]
    assert len(memory.entities) == 1


@pytest.mark.asyncio
async def test_entity_service_keeps_person_descriptors_as_aliases():
    memory = FakeEntityMemoryService()
    service = EntityService(memory)

    row = await service.create_entity(
        EntityCreateRequest(
            entity_type="person",
            display_name="Melissa",
            normalized_name="Melissa",
            relationship="Girl from work",
            summary="Melissa is the coworker involved in the next-week date plan.",
            importance=4,
        )
    )

    assert row["display_name"] == "Melissa"
    assert row["normalized_name"] == "melissa"
    assert row["aliases"] == ["girl from work", "coworker"]


@pytest.mark.asyncio
async def test_entity_event_update_and_deactivate_failure_paths():
    memory = FakeEntityMemoryService()
    service = EntityService(memory)

    event = await service.create_entity_event(
        EntityEventCreateRequest(
            entity_id="entity-1",
            event_type="interaction",
            title="  Coffee  ",
            content="  Talked with Clara after work.  ",
        )
    )

    assert event["title"] == "Coffee"
    assert event["content"] == "Talked with Clara after work."

    updated = await service.update_entity_event(
        event["id"],
        EntityEventUpdateRequest(content="Talked again at lunch."),
    )
    assert updated["content"] == "Talked again at lunch."

    deactivated = await service.deactivate_entity_event(event["id"])
    assert deactivated["active"] is False

    with pytest.raises(EntityServiceError) as error:
        await service.update_entity_event(
            "missing",
            EntityEventUpdateRequest(content="Missing."),
        )
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_entity_service_maps_repository_errors_without_real_supabase():
    service = EntityService(
        FakeEntityMemoryService(MemoryServiceError("Supabase failed.", 503))
    )

    with pytest.raises(EntityServiceError) as error:
        await service.list_entities()

    assert error.value.status_code == 503
    assert error.value.detail == "Supabase failed."
