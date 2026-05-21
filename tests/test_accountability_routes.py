import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_accountability_service, get_memory_service
from app.main import app
from app.models.accountability import AccountabilitySignal, AccountabilitySourceRef
from app.services.memory_service import MemoryServiceError


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeMemoryService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []
        self.rules = [_rule_row()]
        self.commitments = [
            _commitment_row(id="commitment-open", status="open"),
            _commitment_row(id="commitment-done", status="completed"),
        ]
        self.plans = [_plan_row()]
        self.milestones = [
            _milestone_row(id="milestone-open", status="open"),
            _milestone_row(id="milestone-done", status="completed"),
        ]
        self.entities = [_entity_row()]
        self.entity_events = [_entity_event_row()]
        self.memories = [_memory_row()]
        self.memory_candidates = [_memory_candidate_row()]

    def _raise_if_configured(self):
        if self.error is not None:
            raise self.error

    async def list_personal_rules(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("rules", kwargs))
        return self.rules

    async def list_commitments(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("commitments", kwargs))
        return self.commitments

    async def list_plans(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("plans", kwargs))
        return self.plans

    async def list_plan_milestones(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("milestones", kwargs))
        return self.milestones

    async def list_entities(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("entities", kwargs))
        return self.entities

    async def list_entity_events(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("entity_events", kwargs))
        return self.entity_events

    async def get_relevant_memories(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("memories", kwargs))
        return self.memories

    async def list_memory_candidates(self, **kwargs):
        self._raise_if_configured()
        self.calls.append(("memory_candidates", kwargs))
        return self.memory_candidates


class EmptyMemoryService(FakeMemoryService):
    def __init__(self):
        super().__init__()
        self.rules = []
        self.commitments = []
        self.plans = []
        self.milestones = []
        self.entities = []
        self.entity_events = []
        self.memories = []
        self.memory_candidates = []


class FakeAccountabilityService:
    def __init__(self, signals=None, error=None):
        self.signals = signals or []
        self.error = error
        self.calls = []

    async def analyze_signals(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        return self.signals


def test_list_accountability_signals_filters_by_severity_status_and_source(client):
    memory_service = FakeMemoryService()
    accountability_service = FakeAccountabilityService(
        signals=[
            _signal(
                "rule_violation",
                severity="high",
                source_type="personal_rule",
                source_id="rule-1",
            ),
            _signal(
                "rule_violation",
                severity="low",
                source_type="personal_rule",
                source_id="rule-2",
            ),
            _signal(
                "missed_commitment",
                severity="high",
                source_type="commitment",
                source_id="commitment-1",
                status="dismissed",
            ),
        ]
    )
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = (
        lambda: accountability_service
    )

    response = client.get(
        "/accountability/signals"
        "?message=I%20ordered%20DoorDash%20again"
        "&severity=high"
        "&source_type=personal_rule"
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["signal_type"] == "rule_violation"
    assert payload[0]["severity"] == "high"
    assert payload[0]["source_refs"][0]["source_id"] == "rule-1"
    assert accountability_service.calls[0]["message"] == "I ordered DoorDash again"
    assert accountability_service.calls[0]["personal_rules"] == [_rule_row()]
    assert ("rules", {"active": True, "status": "active", "limit": 50}) in (
        memory_service.calls
    )
    assert ("memories", {"query": "I ordered DoorDash again", "limit": 50}) in (
        memory_service.calls
    )


def test_rule_risks_returns_only_active_rule_violations(client):
    app.dependency_overrides[get_memory_service] = lambda: FakeMemoryService()
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService(
        signals=[
            _signal("rule_violation", severity="medium", source_type="personal_rule"),
            _signal("plan_drift", severity="medium", source_type="plan"),
            _signal(
                "rule_violation",
                severity="medium",
                source_type="personal_rule",
                status="resolved",
            ),
        ]
    )

    response = client.get("/accountability/rule-risks")

    assert response.status_code == 200
    payload = response.json()
    assert [item["signal_type"] for item in payload] == ["rule_violation"]
    assert payload[0]["status"] == "active"


def test_plan_risks_returns_plan_drift_and_upcoming_deadlines(client):
    app.dependency_overrides[get_memory_service] = lambda: FakeMemoryService()
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService(
        signals=[
            _signal("plan_drift", severity="high", source_type="plan"),
            _signal("upcoming_deadline", severity="medium", source_type="plan_milestone"),
            _signal("repeated_pattern", severity="medium", source_type="long_term_memory"),
        ]
    )

    response = client.get("/accountability/plan-risks")

    assert response.status_code == 200
    assert [item["signal_type"] for item in response.json()] == [
        "plan_drift",
        "upcoming_deadline",
    ]


def test_patterns_returns_repeated_pattern_signals(client):
    app.dependency_overrides[get_memory_service] = lambda: FakeMemoryService()
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService(
        signals=[
            _signal("repeated_pattern", severity="medium", source_type="long_term_memory"),
            _signal("rule_violation", severity="medium", source_type="personal_rule"),
        ]
    )

    response = client.get("/accountability/patterns")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["signal_type"] == "repeated_pattern"


def test_overview_returns_backing_context_and_filtered_buckets(client):
    app.dependency_overrides[get_memory_service] = lambda: FakeMemoryService()
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService(
        signals=[
            _signal("rule_violation", severity="high", source_type="personal_rule"),
            _signal("plan_drift", severity="medium", source_type="plan"),
            _signal("upcoming_deadline", severity="medium", source_type="plan_milestone"),
            _signal("repeated_pattern", severity="low", source_type="long_term_memory"),
            _signal(
                "missed_commitment",
                severity="medium",
                source_type="commitment",
                status="dismissed",
            ),
        ]
    )

    response = client.get("/accountability/overview?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["signal_count"] == 4
    assert payload["metadata"]["active_rule_count"] == 1
    assert payload["metadata"]["open_commitment_count"] == 1
    assert payload["metadata"]["open_milestone_count"] == 1
    assert payload["metadata"]["completed_milestone_count"] == 1
    assert payload["metadata"]["active_plan_count"] == 1
    assert payload["metadata"]["open_task_count"] == 1
    assert payload["metadata"]["pending_memory_candidate_count"] == 1
    assert [item["id"] for item in payload["open_commitments"]] == ["commitment-open"]
    assert [item["id"] for item in payload["open_milestones"]] == ["milestone-open"]
    assert [item["id"] for item in payload["completed_milestones"]] == [
        "milestone-done"
    ]
    assert [item["id"] for item in payload["pending_memory_candidates"]] == [
        "candidate-1"
    ]
    assert payload["plan_hierarchy"] == [
        {
            "plan": _plan_row(),
            "open_milestones": [
                {
                    **_milestone_row(id="milestone-open", status="open"),
                    "open_commitments": [],
                }
            ],
            "completed_milestones": [
                _milestone_row(id="milestone-done", status="completed")
            ],
            "open_commitments": [],
            "counts": {
                "open_milestones": 1,
                "completed_milestones": 1,
                "open_commitments": 0,
            },
        }
    ]
    assert [item["signal_type"] for item in payload["rule_risks"]] == [
        "rule_violation"
    ]
    assert [item["signal_type"] for item in payload["plan_risks"]] == [
        "plan_drift",
        "upcoming_deadline",
    ]
    assert [item["signal_type"] for item in payload["recent_patterns"]] == [
        "repeated_pattern"
    ]


def test_empty_overview_returns_empty_lists(client):
    app.dependency_overrides[get_memory_service] = lambda: EmptyMemoryService()
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["signals"] == []
    assert payload["active_rules"] == []
    assert payload["open_commitments"] == []
    assert payload["active_plans"] == []
    assert payload["open_milestones"] == []
    assert payload["completed_milestones"] == []
    assert payload["plan_hierarchy"] == []
    assert payload["pending_memory_candidates"] == []
    assert payload["duplicate_warnings"] == []


def test_overview_groups_linked_commitments_under_plan_hierarchy(client):
    memory_service = FakeMemoryService()
    memory_service.commitments = [
        _commitment_row(id="commitment-plan", plan_id="plan-1"),
        _commitment_row(id="commitment-milestone", milestone_id="milestone-open"),
    ]
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    hierarchy = payload["plan_hierarchy"][0]
    assert [item["id"] for item in hierarchy["open_commitments"]] == [
        "commitment-plan"
    ]
    assert [
        item["id"]
        for item in hierarchy["open_milestones"][0]["open_commitments"]
    ] == ["commitment-milestone"]
    assert hierarchy["counts"]["open_commitments"] == 2


def test_overview_reports_duplicate_plan_and_rule_warnings(client):
    memory_service = FakeMemoryService()
    memory_service.plans = [
        _plan_row(id="plan-1", title="Relocate to Europe next year"),
        _plan_row(id="plan-2", title="Relocate to Europe next year"),
    ]
    memory_service.rules = [
        _rule_row(id="rule-1", title="No DoorDash"),
        _rule_row(id="rule-2", title="No DoorDash"),
    ]
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["duplicate_warning_count"] == 2
    assert {item["record_type"] for item in payload["duplicate_warnings"]} == {
        "plan",
        "rule",
    }


def test_overview_reports_duplicate_milestone_and_commitment_warnings(client):
    memory_service = FakeMemoryService()
    memory_service.milestones = [
        _milestone_row(id="milestone-1", title="Date with Melissa next week"),
        _milestone_row(id="milestone-2", title="Next week date with Melissa"),
    ]
    memory_service.commitments = [
        _commitment_row(id="commitment-1", title="No DoorDash"),
        _commitment_row(id="commitment-2", title="Avoid DoorDash"),
    ]
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    warning_types = {item["record_type"] for item in payload["duplicate_warnings"]}
    assert "milestone" in warning_types
    assert "commitment" in warning_types


def test_overview_reports_entity_fact_conflict_warning(client):
    memory_service = FakeMemoryService()
    memory_service.entities = [
        _entity_row(
            id="entity-stephanie",
            display_name="Stephanie",
            summary="Friend who got fired and later quit last month.",
        )
    ]
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    assert any(
        warning["record_type"] == "entity"
        and warning["reason"] == "possible_conflicting_entity_facts"
        for warning in payload["duplicate_warnings"]
    )


def test_overview_does_not_report_negated_fired_fact_as_conflict(client):
    memory_service = FakeMemoryService()
    memory_service.entities = [
        _entity_row(
            id="entity-stephanie",
            display_name="Stephanie",
            summary=(
                "Lara's friend who lives with her; quit about a month ago. "
                "Stephanie was not fired at the beginning of this year."
            ),
        )
    ]
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    assert not any(
        warning["record_type"] == "entity"
        and warning["reason"] == "possible_conflicting_entity_facts"
        for warning in payload["duplicate_warnings"]
    )


def test_overview_reports_plan_cleanup_warning_for_noisy_milestones(client):
    memory_service = FakeMemoryService()
    memory_service.milestones = [
        _milestone_row(id=f"milestone-{index}", title=f"Repeated goal {index}")
        for index in range(8)
    ]
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    assert any(
        warning["record_type"] == "plan"
        and warning["reason"]
        == "plan_open_milestone_count_exceeds_cleanup_threshold"
        for warning in payload["duplicate_warnings"]
    )


def test_overview_reports_semantic_duplicate_plan_warnings(client):
    memory_service = FakeMemoryService()
    memory_service.plans = [
        _plan_row(
            id="plan-1",
            title="Relocate to Europe next year",
            description="Leave the USA next year to live in Europe.",
        ),
        _plan_row(
            id="plan-2",
            title="Estonia e-residency application",
            description="Apply for Estonia e-residency to establish EU business presence.",
        ),
        _plan_row(
            id="plan-3",
            title="European relocation via Italian citizenship",
            description="Pursue Italian citizenship while preparing the physical Europe move.",
        ),
    ]
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/overview")

    assert response.status_code == 200
    payload = response.json()
    plan_warnings = [
        item for item in payload["duplicate_warnings"] if item["record_type"] == "plan"
    ]
    assert len(plan_warnings) == 1
    assert set(plan_warnings[0]["record_ids"]) == {"plan-1", "plan-2", "plan-3"}


def test_invalid_filters_return_validation_errors(client):
    app.dependency_overrides[get_memory_service] = lambda: FakeMemoryService()
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService()

    response = client.get("/accountability/signals?severity=urgent&limit=0")

    assert response.status_code == 422


def test_memory_service_errors_are_returned_without_calling_accountability(client):
    accountability_service = FakeAccountabilityService()
    app.dependency_overrides[get_memory_service] = lambda: FakeMemoryService(
        error=MemoryServiceError("Supabase memory returned an error.", status_code=503)
    )
    app.dependency_overrides[get_accountability_service] = lambda: accountability_service

    response = client.get("/accountability/signals")

    assert response.status_code == 503
    assert response.json() == {"detail": "Supabase memory returned an error."}
    assert accountability_service.calls == []


def test_accountability_service_errors_return_500(client):
    app.dependency_overrides[get_memory_service] = lambda: FakeMemoryService()
    app.dependency_overrides[get_accountability_service] = lambda: FakeAccountabilityService(
        error=RuntimeError("boom")
    )

    response = client.get("/accountability/signals")

    assert response.status_code == 500
    assert response.json() == {"detail": "Accountability analysis failed."}


def _signal(
    signal_type: str,
    *,
    severity: str,
    source_type: str,
    source_id: str = "source-1",
    status: str = "active",
) -> AccountabilitySignal:
    return AccountabilitySignal(
        signal_type=signal_type,
        title=f"{signal_type} title",
        summary=f"{signal_type} summary",
        reason=f"{signal_type} reason",
        severity=severity,
        status=status,
        source_refs=[
            AccountabilitySourceRef(
                source_type=source_type,
                source_id=source_id,
                title=f"{source_type} source",
            )
        ],
    )


def _rule_row(id="rule-1", title="No delivery") -> dict:
    return {
        "id": id,
        "rule_type": "food_delivery",
        "title": title,
        "rule_text": "No DoorDash this week.",
        "trigger_keywords": ["doordash"],
        "priority": 4,
        "status": "active",
        "active": True,
    }


def _commitment_row(
    id="commitment-1",
    title="Workout",
    status="open",
    plan_id=None,
    milestone_id=None,
) -> dict:
    return {
        "id": id,
        "commitment_type": "habit",
        "title": title,
        "commitment_text": "Work out tomorrow morning.",
        "plan_id": plan_id,
        "milestone_id": milestone_id,
        "status": status,
        "active": True,
    }


def _plan_row(id="plan-1", title="Ship Rex", description="") -> dict:
    return {
        "id": id,
        "plan_type": "career",
        "title": title,
        "description": description,
        "status": "active",
        "active": True,
    }


def _milestone_row(
    id="milestone-1",
    status="open",
    title="Release accountability page",
) -> dict:
    return {
        "id": id,
        "plan_id": "plan-1",
        "title": title,
        "status": status,
        "active": True,
    }


def _entity_row(
    id="entity-1",
    display_name="Rex",
    summary="Personal AI assistant.",
) -> dict:
    return {
        "id": id,
        "display_name": display_name,
        "summary": summary,
        "relationship": "project",
        "aliases": [],
        "active": True,
    }


def _entity_event_row() -> dict:
    return {
        "id": "event-1",
        "entity_id": "entity-1",
        "event_type": "interaction",
        "content": "Discussed delivery spending again.",
        "active": True,
    }


def _memory_row() -> dict:
    return {
        "id": "memory-1",
        "memory_type": "preference",
        "content": "I want Rex to call out repeated spending patterns.",
        "active": True,
        "importance": 4,
    }


def _memory_candidate_row() -> dict:
    return {
        "id": "candidate-1",
        "candidate_type": "plan_update",
        "status": "pending",
        "risk_level": "medium",
        "preview": "Update relocation plan description.",
        "reason": "User correction requires confirmation.",
        "active": True,
    }
