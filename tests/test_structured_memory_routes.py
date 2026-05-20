import pytest
from fastapi.testclient import TestClient

from app.dependencies import (
    get_commitment_service,
    get_entity_service,
    get_plan_service,
    get_rule_service,
)
from app.main import app
from app.services.commitment_service import CommitmentServiceError
from app.services.entity_service import EntityServiceError
from app.services.plan_service import PlanServiceError
from app.services.rule_service import RuleServiceError


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeEntityService:
    def __init__(self, error=None):
        self.error = error
        self.list_call = None
        self.created_event = None

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def list_entities(
        self, *, entity_type=None, normalized_name=None, active=True, limit=50
    ):
        self._raise_if_configured()
        self.list_call = {
            "entity_type": entity_type,
            "normalized_name": normalized_name,
            "active": active,
            "limit": limit,
        }
        return [_entity_row()]

    async def create_entity(self, request):
        self._raise_if_configured()
        return {
            **_entity_row(),
            "display_name": request.display_name,
            "normalized_name": request.normalized_name,
        }

    async def update_entity(self, entity_id, request):
        self._raise_if_configured()
        return {**_entity_row(), "id": entity_id, **request.model_dump(exclude_none=True)}

    async def deactivate_entity(self, entity_id):
        self._raise_if_configured()
        return {**_entity_row(), "id": entity_id, "active": False}

    async def list_entity_events(
        self, *, entity_id=None, event_type=None, active=True, limit=50
    ):
        self._raise_if_configured()
        return [_entity_event_row(entity_id=entity_id)]

    async def create_entity_event(self, request):
        self._raise_if_configured()
        self.created_event = request
        return _entity_event_row(entity_id=request.entity_id, content=request.content)

    async def update_entity_event(self, event_id, request):
        self._raise_if_configured()
        return {
            **_entity_event_row(),
            "id": event_id,
            **request.model_dump(exclude_none=True),
        }

    async def deactivate_entity_event(self, event_id):
        self._raise_if_configured()
        return {**_entity_event_row(), "id": event_id, "active": False}


class FakeRuleService:
    def __init__(self, error=None):
        self.error = error

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def list_rules(self, *, rule_type=None, status=None, active=True, limit=50):
        self._raise_if_configured()
        return [_rule_row(rule_type=rule_type or "finance")]

    async def create_rule(self, request):
        self._raise_if_configured()
        return _rule_row(
            rule_type=request.rule_type,
            title=request.title,
            rule_text=request.rule_text,
        )

    async def update_rule(self, rule_id, request):
        self._raise_if_configured()
        return {**_rule_row(), "id": rule_id, **request.model_dump(exclude_none=True)}

    async def deactivate_rule(self, rule_id):
        self._raise_if_configured()
        return {**_rule_row(), "id": rule_id, "active": False}


class FakePlanService:
    def __init__(self, error=None):
        self.error = error

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def list_plans(self, *, plan_type=None, status=None, active=True, limit=50):
        self._raise_if_configured()
        return [_plan_row(plan_type=plan_type or "finance")]

    async def create_plan(self, request):
        self._raise_if_configured()
        return _plan_row(plan_type=request.plan_type, title=request.title)

    async def update_plan(self, plan_id, request):
        self._raise_if_configured()
        return {**_plan_row(), "id": plan_id, **request.model_dump(exclude_none=True)}

    async def deactivate_plan(self, plan_id):
        self._raise_if_configured()
        return {**_plan_row(), "id": plan_id, "active": False}

    async def list_milestones(
        self, *, plan_id=None, status=None, active=True, limit=50
    ):
        self._raise_if_configured()
        return [_milestone_row(plan_id=plan_id)]

    async def create_milestone(self, request):
        self._raise_if_configured()
        return _milestone_row(plan_id=request.plan_id, title=request.title)

    async def update_milestone(self, milestone_id, request):
        self._raise_if_configured()
        return {
            **_milestone_row(),
            "id": milestone_id,
            **request.model_dump(exclude_none=True),
        }

    async def deactivate_milestone(self, milestone_id):
        self._raise_if_configured()
        return {**_milestone_row(), "id": milestone_id, "active": False}


class FakeCommitmentService:
    def __init__(self, error=None):
        self.error = error

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def list_commitments(
        self, *, commitment_type=None, milestone_id=None, status=None, active=True, limit=50
    ):
        self._raise_if_configured()
        return [_commitment_row(commitment_type=commitment_type or "task")]

    async def create_commitment(self, request):
        self._raise_if_configured()
        return _commitment_row(
            commitment_type=request.commitment_type,
            title=request.title,
            commitment_text=request.commitment_text,
        )

    async def update_commitment(self, commitment_id, request):
        self._raise_if_configured()
        return {
            **_commitment_row(),
            "id": commitment_id,
            **request.model_dump(exclude_none=True),
        }

    async def deactivate_commitment(self, commitment_id):
        self._raise_if_configured()
        return {**_commitment_row(), "id": commitment_id, "active": False}


def test_list_entities_uses_filters_and_response_model(client):
    fake_service = FakeEntityService()
    app.dependency_overrides[get_entity_service] = lambda: fake_service

    response = client.get(
        "/entities?entity_type=person&normalized_name=pedro&active=true&limit=10"
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == "entity-1"
    assert fake_service.list_call == {
        "entity_type": "person",
        "normalized_name": "pedro",
        "active": True,
        "limit": 10,
    }


def test_create_entity_event_rejects_entity_id_mismatch(client):
    app.dependency_overrides[get_entity_service] = lambda: FakeEntityService()

    response = client.post(
        "/entities/entity-1/events",
        json={"entity_id": "entity-2", "content": "Saw him at coffee."},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Entity ID mismatch."


def test_entity_routes_map_service_errors(client):
    app.dependency_overrides[get_entity_service] = lambda: FakeEntityService(
        EntityServiceError("Entity not found.", 404)
    )

    response = client.patch("/entities/missing", json={"summary": "Updated."})

    assert response.status_code == 404
    assert response.json()["detail"] == "Entity not found."


def test_create_entity_rejects_invalid_schema_payload(client):
    app.dependency_overrides[get_entity_service] = lambda: FakeEntityService()

    response = client.post(
        "/entities",
        json={
            "entity_type": "person",
            "display_name": "Clara",
            "normalized_name": "clara",
            "importance": 9,
        },
    )

    assert response.status_code == 422


def test_rule_crud_routes(client):
    app.dependency_overrides[get_rule_service] = lambda: FakeRuleService()

    create_response = client.post(
        "/rules",
        json={
            "rule_type": "finance",
            "title": "No Uber",
            "rule_text": "Use transit unless it is unsafe.",
        },
    )
    update_response = client.patch("/rules/rule-1", json={"priority": 5})
    delete_response = client.delete("/rules/rule-1")

    assert create_response.status_code == 201
    assert create_response.json()["rule_type"] == "finance"
    assert update_response.status_code == 200
    assert update_response.json()["priority"] == 5
    assert delete_response.status_code == 204


def test_rule_routes_map_service_errors(client):
    app.dependency_overrides[get_rule_service] = lambda: FakeRuleService(
        RuleServiceError("Personal rule not found.", 404)
    )

    response = client.patch("/rules/missing", json={"priority": 5})

    assert response.status_code == 404
    assert response.json()["detail"] == "Personal rule not found."


def test_create_rule_rejects_invalid_schema_payload(client):
    app.dependency_overrides[get_rule_service] = lambda: FakeRuleService()

    response = client.post(
        "/rules",
        json={
            "rule_type": "finance",
            "title": "No DoorDash",
            "rule_text": "Avoid delivery.",
            "priority": 8,
        },
    )

    assert response.status_code == 422


def test_plan_routes_include_nested_milestones(client):
    app.dependency_overrides[get_plan_service] = lambda: FakePlanService()

    plan_response = client.post(
        "/plans",
        json={"plan_type": "immigration", "title": "Move abroad"},
    )
    milestone_response = client.post(
        "/plans/plan-1/milestones",
        json={
            "plan_id": "plan-1",
            "title": "Submit documents",
            "milestone_type": "deadline",
        },
    )
    list_response = client.get("/plans/plan-1/milestones?status=open")

    assert plan_response.status_code == 201
    assert plan_response.json()["title"] == "Move abroad"
    assert milestone_response.status_code == 201
    assert milestone_response.json()["plan_id"] == "plan-1"
    assert list_response.status_code == 200
    assert list_response.json()[0]["status"] == "open"


def test_create_plan_rejects_invalid_schema_payload(client):
    app.dependency_overrides[get_plan_service] = lambda: FakePlanService()

    response = client.post(
        "/plans",
        json={"plan_type": "unknown", "title": "Move abroad"},
    )

    assert response.status_code == 422


def test_plan_milestone_rejects_plan_id_mismatch(client):
    app.dependency_overrides[get_plan_service] = lambda: FakePlanService()

    response = client.post(
        "/plans/plan-1/milestones",
        json={"plan_id": "plan-2", "title": "Submit documents"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Plan ID mismatch."


def test_plan_routes_map_service_errors(client):
    app.dependency_overrides[get_plan_service] = lambda: FakePlanService(
        PlanServiceError("Plan not found.", 404)
    )

    response = client.delete("/plans/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Plan not found."


def test_commitment_crud_routes(client):
    app.dependency_overrides[get_commitment_service] = lambda: FakeCommitmentService()

    create_response = client.post(
        "/commitments",
        json={
            "commitment_type": "health",
            "title": "Workout",
            "commitment_text": "Work out tomorrow morning.",
        },
    )
    list_response = client.get("/commitments?commitment_type=health&status=open")
    update_response = client.patch("/commitments/commitment-1", json={"status": "missed"})
    delete_response = client.delete("/commitments/commitment-1")

    assert create_response.status_code == 201
    assert create_response.json()["commitment_type"] == "health"
    assert list_response.status_code == 200
    assert list_response.json()[0]["status"] == "open"
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "missed"
    assert delete_response.status_code == 204


def test_create_commitment_rejects_invalid_schema_payload(client):
    app.dependency_overrides[get_commitment_service] = lambda: FakeCommitmentService()

    response = client.post(
        "/commitments",
        json={
            "commitment_type": "health",
            "title": "Workout",
            "commitment_text": "Work out tomorrow morning.",
            "priority": 0,
        },
    )

    assert response.status_code == 422


def test_commitment_routes_map_service_errors(client):
    app.dependency_overrides[get_commitment_service] = lambda: FakeCommitmentService(
        CommitmentServiceError("Commitment not found.", 404)
    )

    response = client.delete("/commitments/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Commitment not found."


def _entity_row(**overrides):
    return {
        "id": "entity-1",
        "entity_type": "person",
        "display_name": "Pedro Martins",
        "normalized_name": "pedro martins",
        "aliases": [],
        "importance": 3,
        "status": "active",
        "active": True,
        "metadata": {},
        **overrides,
    }


def _entity_event_row(**overrides):
    return {
        "id": "event-1",
        "entity_id": "entity-1",
        "event_type": "note",
        "content": "Met for coffee.",
        "importance": 3,
        "active": True,
        "metadata": {},
        **overrides,
    }


def _rule_row(**overrides):
    return {
        "id": "rule-1",
        "rule_type": "finance",
        "title": "No Uber",
        "rule_text": "Use transit unless it is unsafe.",
        "trigger_keywords": [],
        "enforcement_style": "gentle_direct",
        "priority": 3,
        "status": "active",
        "active": True,
        "metadata": {},
        **overrides,
    }


def _plan_row(**overrides):
    return {
        "id": "plan-1",
        "plan_type": "finance",
        "title": "Move abroad",
        "priority": 3,
        "status": "active",
        "active": True,
        "metadata": {},
        **overrides,
    }


def _milestone_row(**overrides):
    return {
        "id": "milestone-1",
        "plan_id": "plan-1",
        "title": "Save first target",
        "milestone_type": "goal",
        "priority": 3,
        "status": "open",
        "active": True,
        "metadata": {},
        **overrides,
    }


def _commitment_row(**overrides):
    return {
        "id": "commitment-1",
        "commitment_type": "task",
        "title": "Workout",
        "commitment_text": "Work out tomorrow morning.",
        "priority": 3,
        "status": "open",
        "active": True,
        "metadata": {},
        **overrides,
    }
