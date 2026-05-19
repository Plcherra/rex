import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_memory_service
from app.main import app
from app.services.memory_service import MemoryServiceError


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeMemoryManagementService:
    def __init__(self, error=None):
        self.error = error
        self.memories = [
            {
                "id": "memory-1",
                "memory_type": "preference",
                "content": "I prefer direct advice.",
                "source_conversation_id": "conversation-1",
                "source_message_id": "message-1",
                "importance": 4,
                "active": True,
                "superseded_by": None,
                "confidence": 0.75,
                "correction_group": None,
                "metadata": {},
                "created_at": "2026-05-11T10:00:00Z",
                "updated_at": "2026-05-11T10:00:00Z",
                "last_accessed_at": "2026-05-11T10:00:00Z",
            },
            {
                "id": "memory-2",
                "memory_type": "event",
                "content": "I started a new job.",
                "source_conversation_id": None,
                "source_message_id": None,
                "importance": 3,
                "active": False,
                "superseded_by": None,
                "confidence": 0.75,
                "correction_group": None,
                "metadata": {},
                "created_at": "2026-05-10T10:00:00Z",
                "updated_at": "2026-05-10T10:00:00Z",
                "last_accessed_at": "2026-05-10T10:00:00Z",
            },
        ]
        self.corrections = [
            {
                "id": "correction-1",
                "correction_type": "entity_name",
                "old_value": "al",
                "new_value": "melissa",
                "target_table": "long_term_memory",
                "target_id": "memory-1",
                "source_conversation_id": "conversation-1",
                "source_message_id": "message-1",
                "applied": True,
                "confidence": 0.9,
                "metadata": {"correction_group": "correction:al->melissa"},
                "created_at": "2026-05-19T10:00:00Z",
            }
        ]
        self.list_calls = []
        self.correction_list_calls = []

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def list_long_term_memory(self, limit=50, memory_type=None, active=None):
        self._raise_if_configured()
        self.list_calls.append(
            {
                "limit": limit,
                "memory_type": memory_type,
                "active": active,
            }
        )
        results = self.memories
        if memory_type is not None:
            results = [
                memory for memory in results if memory["memory_type"] == memory_type
            ]
        if active is not None:
            results = [memory for memory in results if memory["active"] is active]
        return results[:limit]

    async def update_long_term_memory(self, memory_id, **updates):
        self._raise_if_configured()
        for memory in self.memories:
            if memory["id"] == memory_id:
                memory.update(updates)
                return memory
        return None

    async def deactivate_long_term_memory(self, memory_id):
        self._raise_if_configured()
        memory = await self.update_long_term_memory(memory_id, active=False)
        return memory is not None

    async def list_memory_corrections(
        self,
        limit=50,
        correction_type=None,
        applied=None,
        target_table=None,
        target_id=None,
    ):
        self._raise_if_configured()
        self.correction_list_calls.append(
            {
                "limit": limit,
                "correction_type": correction_type,
                "applied": applied,
                "target_table": target_table,
                "target_id": target_id,
            }
        )
        results = self.corrections
        if correction_type is not None:
            results = [
                correction
                for correction in results
                if correction["correction_type"] == correction_type
            ]
        if applied is not None:
            results = [
                correction
                for correction in results
                if correction["applied"] is applied
            ]
        if target_table is not None:
            results = [
                correction
                for correction in results
                if correction["target_table"] == target_table
            ]
        if target_id is not None:
            results = [
                correction
                for correction in results
                if correction["target_id"] == target_id
            ]
        return results[:limit]


def override_memory_service(fake_memory_service):
    app.dependency_overrides[get_memory_service] = lambda: fake_memory_service


def test_list_memory_supports_filters(client):
    fake_memory_service = FakeMemoryManagementService()
    override_memory_service(fake_memory_service)

    response = client.get("/memory?memory_type=preference&active=true&limit=10")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "memory-1"
    assert data[0]["memory_type"] == "preference"
    assert fake_memory_service.list_calls == [
        {"limit": 10, "memory_type": "preference", "active": True}
    ]


def test_list_memory_validates_limit(client):
    override_memory_service(FakeMemoryManagementService())

    response = client.get("/memory?limit=0")

    assert response.status_code == 422


def test_list_memory_maps_service_errors(client):
    override_memory_service(
        FakeMemoryManagementService(
            error=MemoryServiceError("Supabase unavailable.", status_code=503)
        )
    )

    response = client.get("/memory")

    assert response.status_code == 503
    assert response.json()["detail"] == "Supabase unavailable."


def test_patch_memory_updates_content_and_importance(client):
    override_memory_service(FakeMemoryManagementService())

    response = client.patch(
        "/memory/memory-1",
        json={
            "content": "I prefer blunt advice.",
            "importance": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "I prefer blunt advice."
    assert data["importance"] == 5


def test_patch_memory_updates_audit_fields(client):
    override_memory_service(FakeMemoryManagementService())

    response = client.patch(
        "/memory/memory-1",
        json={
            "active": False,
            "superseded_by": "memory-2",
            "confidence": 0.9,
            "correction_group": "correction:al->melissa",
            "metadata": {"reason": "manual correction"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["active"] is False
    assert data["superseded_by"] == "memory-2"
    assert data["confidence"] == 0.9
    assert data["correction_group"] == "correction:al->melissa"
    assert data["metadata"] == {"reason": "manual correction"}


def test_list_memory_corrections_supports_filters(client):
    fake_memory_service = FakeMemoryManagementService()
    override_memory_service(fake_memory_service)

    response = client.get(
        "/memory/corrections?correction_type=entity_name"
        "&applied=true&target_table=long_term_memory&target_id=memory-1"
        "&limit=10"
    )

    assert response.status_code == 200
    data = response.json()
    assert [correction["id"] for correction in data] == ["correction-1"]
    assert fake_memory_service.correction_list_calls == [
        {
            "limit": 10,
            "correction_type": "entity_name",
            "applied": True,
            "target_table": "long_term_memory",
            "target_id": "memory-1",
        }
    ]


def test_patch_memory_validates_importance(client):
    override_memory_service(FakeMemoryManagementService())

    response = client.patch("/memory/memory-1", json={"importance": 9})

    assert response.status_code == 422


def test_patch_memory_rejects_empty_update(client):
    override_memory_service(FakeMemoryManagementService())

    response = client.patch("/memory/memory-1", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "At least one memory field must be provided."


def test_patch_memory_returns_404_for_missing_memory(client):
    override_memory_service(FakeMemoryManagementService())

    response = client.patch("/memory/missing", json={"content": "Updated"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found."


def test_delete_memory_deactivates_memory(client):
    fake_memory_service = FakeMemoryManagementService()
    override_memory_service(fake_memory_service)

    response = client.delete("/memory/memory-1")

    assert response.status_code == 204
    assert fake_memory_service.memories[0]["active"] is False


def test_delete_memory_returns_404_for_missing_memory(client):
    override_memory_service(FakeMemoryManagementService())

    response = client.delete("/memory/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found."
