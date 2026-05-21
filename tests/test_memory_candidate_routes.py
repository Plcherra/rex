import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_memory_candidate_service
from app.main import app
from app.services.memory_candidate_service import MemoryCandidateServiceError


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeMemoryCandidateService:
    def __init__(self, error=None):
        self.error = error
        self.created = None
        self.list_call = None
        self.updated = None

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def create_candidate(self, request):
        self._raise_if_configured()
        self.created = request
        return _candidate_row(
            candidate_type=request.candidate_type,
            payload=request.payload,
            risk_level=request.risk_level,
        )

    async def list_candidates(
        self,
        *,
        candidate_type=None,
        status=None,
        risk_level=None,
        source_conversation_id=None,
        limit=50,
    ):
        self._raise_if_configured()
        self.list_call = {
            "candidate_type": candidate_type,
            "status": status,
            "risk_level": risk_level,
            "source_conversation_id": source_conversation_id,
            "limit": limit,
        }
        return [_candidate_row(candidate_type=candidate_type or "plan")]

    async def update_candidate(self, candidate_id, request):
        self._raise_if_configured()
        self.updated = request
        return _candidate_row(id=candidate_id, payload=request.payload or {"title": "Updated"})

    async def approve_candidate(self, candidate_id, request):
        self._raise_if_configured()
        return _candidate_row(
            id=candidate_id,
            status="approved",
            approved_by=request.approved_by,
            decision={"durable_apply_enabled": False},
        )

    async def reject_candidate(self, candidate_id, request):
        self._raise_if_configured()
        return _candidate_row(id=candidate_id, status="rejected", reason=request.reason)

    async def bulk_approve_candidates(self, request):
        self._raise_if_configured()
        return {
            "approved": [_candidate_row(status="approved")],
            "rejected": [],
            "skipped": [_candidate_row(id="candidate-high", risk_level="high")],
        }

    async def bulk_reject_candidates(self, request):
        self._raise_if_configured()
        return {
            "approved": [],
            "rejected": [_candidate_row(status="rejected")],
            "skipped": [],
        }


def test_create_and_list_memory_candidates(client):
    fake_service = FakeMemoryCandidateService()
    app.dependency_overrides[get_memory_candidate_service] = lambda: fake_service

    create_response = client.post(
        "/memory-candidates",
        json={
            "candidate_type": "plan",
            "payload": {"title": "Move out of the country"},
            "risk_level": "high",
            "source_conversation_id": "conversation-1",
        },
    )
    list_response = client.get(
        "/memory-candidates?candidate_type=plan&status=pending&risk_level=high&"
        "source_conversation_id=conversation-1&limit=10"
    )

    assert create_response.status_code == 201
    assert create_response.json()["preview"] == "plan: Move out of the country"
    assert fake_service.created.payload == {"title": "Move out of the country"}
    assert list_response.status_code == 200
    assert fake_service.list_call == {
        "candidate_type": "plan",
        "status": "pending",
        "risk_level": "high",
        "source_conversation_id": "conversation-1",
        "limit": 10,
    }


def test_update_approve_reject_and_bulk_routes(client):
    app.dependency_overrides[get_memory_candidate_service] = (
        lambda: FakeMemoryCandidateService()
    )

    update_response = client.patch(
        "/memory-candidates/candidate-1",
        json={"payload": {"title": "Updated plan"}},
    )
    approve_response = client.post(
        "/memory-candidates/candidate-1/approve",
        json={"approved_by": "pedro"},
    )
    reject_response = client.post(
        "/memory-candidates/candidate-2/reject",
        json={"reason": "Wrong."},
    )
    approve_all_response = client.post(
        "/memory-candidates/approve-all",
        json={"source_conversation_id": "conversation-1"},
    )
    reject_all_response = client.post(
        "/memory-candidates/reject-all",
        json={"candidate_ids": ["candidate-1"]},
    )

    assert update_response.status_code == 200
    assert update_response.json()["payload"] == {"title": "Updated plan"}
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"
    assert approve_response.json()["decision"]["durable_apply_enabled"] is False
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert approve_all_response.status_code == 200
    assert approve_all_response.json()["approved"][0]["status"] == "approved"
    assert approve_all_response.json()["skipped"][0]["risk_level"] == "high"
    assert reject_all_response.status_code == 200
    assert reject_all_response.json()["rejected"][0]["status"] == "rejected"


def test_routes_reject_invalid_schema_payload(client):
    app.dependency_overrides[get_memory_candidate_service] = (
        lambda: FakeMemoryCandidateService()
    )

    response = client.post(
        "/memory-candidates",
        json={
            "candidate_type": "unknown",
            "payload": {"title": "Bad"},
            "risk_level": "high",
        },
    )

    assert response.status_code == 422


def test_routes_map_service_errors(client):
    app.dependency_overrides[get_memory_candidate_service] = (
        lambda: FakeMemoryCandidateService(
            MemoryCandidateServiceError("Candidate not found.", 404)
        )
    )

    response = client.patch(
        "/memory-candidates/missing",
        json={"payload": {"title": "Updated"}},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found."


def _candidate_row(**overrides):
    row = {
        "id": "candidate-1",
        "candidate_type": "plan",
        "payload": {"title": "Move out of the country"},
        "status": "pending",
        "risk_level": "medium",
        "decision": None,
        "reason": None,
        "source_conversation_id": None,
        "source_message_id": None,
        "approved_by": None,
        "approved_at": None,
        "applied_at": None,
        "rejected_at": None,
        "applied_record_table": None,
        "applied_record_id": None,
        "verification": None,
        "preview": "plan: Move out of the country",
        "created_at": "2026-05-21T00:00:00+00:00",
        "updated_at": "2026-05-21T00:00:00+00:00",
    }
    row.update(overrides)
    if "payload" in overrides:
        title = overrides["payload"].get("title", "pending memory change")
        row["preview"] = f"{row['candidate_type']}: {title}"
    return row
