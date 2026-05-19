import pytest
from pydantic import ValidationError

from app.dependencies import get_accountability_service
from app.models.accountability import (
    AccountabilitySignal,
    AccountabilitySourceRef,
)
from app.services.accountability_service import AccountabilityService


def test_accountability_signal_validates_stable_payload_shape():
    signal = AccountabilitySignal(
        signal_type="rule_violation",
        title="DoorDash rule risk",
        summary="The user mentioned ordering DoorDash again.",
        reason="Active food delivery rule matched the current message.",
        severity="high",
        confidence=0.87,
        source_refs=[
            AccountabilitySourceRef(
                source_type="personal_rule",
                source_id="rule-1",
                title="No DoorDash",
                excerpt="Avoid DoorDash while budget is slipping.",
            )
        ],
        suggested_prompt="You said DoorDash was off-limits while the budget is slipping.",
        recommended_action="Ask whether this was already ordered or still avoidable.",
        metadata={"matched_keywords": ["doordash"]},
    )

    payload = signal.model_dump()

    assert payload["signal_type"] == "rule_violation"
    assert payload["severity"] == "high"
    assert payload["confidence"] == 0.87
    assert payload["status"] == "active"
    assert payload["source_refs"][0]["source_type"] == "personal_rule"
    assert payload["metadata"] == {"matched_keywords": ["doordash"]}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("signal_type", "random"),
        ("severity", "extreme"),
        ("status", "pending"),
    ],
)
def test_accountability_signal_rejects_unknown_enums(field, value):
    payload = {
        "signal_type": "missed_commitment",
        "title": "Missed workout",
        "summary": "The workout commitment is overdue.",
        "reason": "Commitment due time has passed.",
        field: value,
    }

    with pytest.raises(ValidationError):
        AccountabilitySignal(**payload)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_accountability_signal_rejects_out_of_range_confidence(confidence):
    with pytest.raises(ValidationError):
        AccountabilitySignal(
            signal_type="plan_drift",
            title="Plan drift",
            summary="The plan is drifting.",
            reason="No update has been recorded recently.",
            confidence=confidence,
        )


@pytest.mark.asyncio
async def test_accountability_service_skeleton_returns_empty_context_metadata():
    service = AccountabilityService()
    message = "Can you review this?"

    context = await service.analyze(
        message=message,
        time_context={"timezone": "America/New_York (EDT)"},
        personal_rules=[{"id": "rule-1"}],
        commitments=[{"id": "commitment-1"}],
        plans=[{"id": "plan-1"}],
        plan_milestones=[{"id": "milestone-1"}],
        entity_events=[{"id": "event-1"}],
        relevant_memories=[{"id": "memory-1"}],
    )

    assert context.signals == []
    assert context.metadata == {
        "message_character_count": len(message),
        "time_context_present": True,
        "personal_rule_count": 1,
        "commitment_count": 1,
        "plan_count": 1,
        "plan_milestone_count": 1,
        "entity_event_count": 1,
        "relevant_memory_count": 1,
    }


@pytest.mark.asyncio
async def test_accountability_service_exposes_list_returning_signal_interface():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I ordered DoorDash again.",
        time_context={"timezone": "America/New_York (EDT)"},
        personal_rules=[{"id": "rule-1"}],
        commitments=[],
        plans=[],
        plan_milestones=[],
        entity_events=[],
        relevant_memories=[],
    )

    assert signals == []


def test_accountability_service_is_dependency_injectable_without_external_clients():
    service = get_accountability_service()

    assert isinstance(service, AccountabilityService)


def test_accountability_service_filters_active_signals():
    service = AccountabilityService()
    active = AccountabilitySignal(
        signal_type="upcoming_deadline",
        title="Deadline soon",
        summary="A deadline is coming up.",
        reason="The milestone target date is near.",
    )
    dismissed = AccountabilitySignal(
        signal_type="budget_risk",
        title="Budget risk",
        summary="Spending risk detected.",
        reason="Repeated spending mentions.",
        status="dismissed",
    )

    assert service.active_signals([active, dismissed]) == [active]


@pytest.mark.asyncio
async def test_accountability_service_detects_food_delivery_rule_violation():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I ordered DoorDash again after work.",
        personal_rules=[
            {
                "id": "rule-doordash",
                "rule_type": "food_delivery",
                "title": "No DoorDash",
                "rule_text": "Do not order DoorDash while the budget is slipping.",
                "trigger_keywords": ["DoorDash"],
                "priority": 5,
                "status": "active",
                "active": True,
                "enforcement_style": "strict",
            }
        ],
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "rule_violation"
    assert signal.severity == "high"
    assert signal.source_refs[0].source_type == "personal_rule"
    assert signal.source_refs[0].source_id == "rule-doordash"
    assert signal.metadata["matched_terms"] == ["doordash"]
    assert signal.metadata["action_terms"] == ["ordered"]
    assert "same pattern again" in signal.suggested_prompt


@pytest.mark.asyncio
async def test_accountability_service_detects_transport_rule_violation():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I took Uber home because I was tired.",
        personal_rules=[
            {
                "id": "rule-uber",
                "rule_type": "transport",
                "title": "Avoid Uber",
                "rule_text": "Take the train instead of Uber unless it is unsafe.",
                "trigger_keywords": ["Uber"],
                "priority": 4,
                "status": "active",
                "active": True,
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].severity == "medium"
    assert signals[0].metadata["matched_terms"] == ["uber"]
    assert signals[0].metadata["action_terms"] == ["took"]


@pytest.mark.asyncio
async def test_accountability_service_detects_finance_rule_from_custom_keywords():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I renewed Netflix even though I meant to cut subscriptions.",
        personal_rules=[
            {
                "id": "rule-subscriptions",
                "rule_type": "finance",
                "title": "Cut subscriptions",
                "rule_text": "No renewing unnecessary subscriptions this month.",
                "trigger_keywords": ["Netflix", "subscriptions"],
                "priority": 4,
                "status": "active",
                "active": True,
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].metadata["matched_terms"] == ["netflix", "subscriptions"]
    assert signals[0].metadata["action_terms"] == ["renewed"]


@pytest.mark.asyncio
async def test_accountability_service_detects_coffee_and_spending_cap_rule():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I spent 12 dollars at Starbucks this morning.",
        personal_rules=[
            {
                "id": "rule-coffee-cap",
                "rule_type": "coffee",
                "title": "Coffee cap",
                "rule_text": "Keep coffee spending under the daily cap.",
                "trigger_keywords": ["Starbucks", "coffee"],
                "priority": 3,
                "status": "active",
                "active": True,
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].severity == "low"
    assert signals[0].metadata["matched_terms"] == ["starbucks"]
    assert signals[0].metadata["action_terms"] == ["spent"]


@pytest.mark.asyncio
async def test_accountability_service_does_not_trigger_for_unrelated_or_inactive_rules():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I ordered a replacement charger.",
        personal_rules=[
            {
                "id": "rule-doordash",
                "rule_type": "food_delivery",
                "title": "No DoorDash",
                "rule_text": "Do not order DoorDash while the budget is slipping.",
                "trigger_keywords": ["DoorDash"],
                "priority": 5,
                "status": "active",
                "active": True,
            },
            {
                "id": "rule-uber",
                "rule_type": "transport",
                "title": "Avoid Uber",
                "rule_text": "Take the train instead of Uber.",
                "trigger_keywords": ["Uber"],
                "priority": 5,
                "status": "paused",
                "active": True,
            },
        ],
    )

    assert signals == []


@pytest.mark.asyncio
async def test_accountability_service_ignores_preventive_rule_mentions():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I did not order DoorDash. I deleted the app.",
        personal_rules=[
            {
                "id": "rule-doordash",
                "rule_type": "food_delivery",
                "title": "No DoorDash",
                "rule_text": "Do not order DoorDash while the budget is slipping.",
                "trigger_keywords": ["DoorDash"],
                "priority": 5,
                "status": "active",
                "active": True,
                "last_reviewed_at": "2026-05-19T09:00:00-04:00",
            }
        ],
    )

    assert signals == []


@pytest.mark.asyncio
async def test_accountability_service_detects_missed_commitment():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="What should I focus on today?",
        time_context={"iso_timestamp": "2026-05-19T15:00:00-04:00"},
        commitments=[
            {
                "id": "commitment-workout",
                "commitment_type": "health",
                "title": "Morning workout",
                "commitment_text": "Work out tomorrow morning.",
                "priority": 5,
                "status": "open",
                "active": True,
                "due_at": "2026-05-19T09:00:00-04:00",
            }
        ],
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "missed_commitment"
    assert signal.severity == "high"
    assert signal.source_refs[0].source_type == "commitment"
    assert signal.source_refs[0].source_id == "commitment-workout"
    assert signal.metadata["overdue_hours"] == 6


@pytest.mark.asyncio
async def test_accountability_service_detects_due_today_commitment():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="What do I still need to do?",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        commitments=[
            {
                "id": "commitment-paperwork",
                "commitment_type": "immigration",
                "title": "Review paperwork",
                "commitment_text": "Review immigration paperwork.",
                "priority": 4,
                "status": "in_progress",
                "active": True,
                "due_at": "2026-05-19T18:00:00-04:00",
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "upcoming_deadline"
    assert signals[0].metadata["subtype"] == "commitment_due_today"
    assert signals[0].metadata["hours_until_due"] == 8


@pytest.mark.asyncio
async def test_accountability_service_detects_reported_commitment_completion():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I finished the immigration paperwork today.",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        commitments=[
            {
                "id": "commitment-paperwork",
                "commitment_type": "immigration",
                "title": "Review paperwork",
                "commitment_text": "Review immigration paperwork.",
                "priority": 4,
                "status": "open",
                "active": True,
                "due_at": "2026-05-19T18:00:00-04:00",
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "positive_follow_through"
    assert signals[0].metadata["subtype"] == "reported_completion"
    assert signals[0].metadata["matched_terms"] == [
        "immigration",
        "paperwork",
    ]


@pytest.mark.asyncio
async def test_accountability_service_detects_commitment_follow_up_need():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="Give me a quick status check.",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        commitments=[
            {
                "id": "commitment-budget",
                "commitment_type": "money",
                "title": "Track grocery spending",
                "commitment_text": "Track grocery spending every week.",
                "priority": 4,
                "status": "open",
                "active": True,
                "last_checked_at": "2026-05-01T10:00:00-04:00",
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "upcoming_deadline"
    assert signals[0].metadata["subtype"] == "commitment_follow_up"
    assert signals[0].source_refs[0].source_id == "commitment-budget"


@pytest.mark.asyncio
async def test_accountability_service_ignores_completed_or_inactive_commitments():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I finished the paperwork.",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        commitments=[
            {
                "id": "commitment-complete",
                "commitment_type": "task",
                "title": "Paperwork",
                "commitment_text": "Finish the paperwork.",
                "priority": 5,
                "status": "completed",
                "active": True,
                "due_at": "2026-05-18T10:00:00-04:00",
            },
            {
                "id": "commitment-inactive",
                "commitment_type": "task",
                "title": "Old workout",
                "commitment_text": "Work out.",
                "priority": 5,
                "status": "open",
                "active": False,
                "due_at": "2026-05-18T10:00:00-04:00",
            },
        ],
    )

    assert signals == []


@pytest.mark.asyncio
async def test_accountability_service_detects_upcoming_plan_milestone():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="What should I focus on this week?",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        plans=[
            {
                "id": "plan-runway",
                "plan_type": "finance",
                "title": "Move-out income target",
                "description": "Build enough income runway to move out.",
                "priority": 5,
                "status": "active",
                "active": True,
                "last_reviewed_at": "2026-05-19T09:00:00-04:00",
            }
        ],
        plan_milestones=[
            {
                "id": "milestone-income",
                "plan_id": "plan-runway",
                "title": "Hit weekly income target",
                "description": "Reach this week's income target.",
                "milestone_type": "deadline",
                "target_date": "2026-05-22",
                "priority": 4,
                "status": "open",
                "active": True,
            }
        ],
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "upcoming_deadline"
    assert signal.metadata["subtype"] == "upcoming_milestone"
    assert signal.metadata["days_until_due"] == 3
    assert signal.source_refs[0].source_type == "plan_milestone"
    assert signal.source_refs[1].source_id == "plan-runway"


@pytest.mark.asyncio
async def test_accountability_service_detects_overdue_plan_milestone():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="Review my plan.",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        plans=[
            {
                "id": "plan-immigration",
                "plan_type": "immigration",
                "title": "Visa runway",
                "priority": 5,
                "status": "active",
                "active": True,
                "last_reviewed_at": "2026-05-19T09:00:00-04:00",
            }
        ],
        plan_milestones=[
            {
                "id": "milestone-docs",
                "plan_id": "plan-immigration",
                "title": "Prepare immigration documents",
                "milestone_type": "deadline",
                "target_date": "2026-05-12",
                "priority": 5,
                "status": "in_progress",
                "active": True,
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "plan_drift"
    assert signals[0].severity == "high"
    assert signals[0].metadata["subtype"] == "overdue_milestone"
    assert signals[0].metadata["days_overdue"] == 7


@pytest.mark.asyncio
async def test_accountability_service_detects_stalled_high_priority_plan():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="Give me a status check.",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        plans=[
            {
                "id": "plan-career",
                "plan_type": "career",
                "title": "Kitchen management promotion",
                "description": "Prepare for a kitchen management role.",
                "priority": 4,
                "status": "active",
                "active": True,
                "last_reviewed_at": "2026-05-01T10:00:00-04:00",
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "plan_drift"
    assert signals[0].metadata["subtype"] == "stalled_plan"
    assert signals[0].source_refs[0].source_id == "plan-career"


@pytest.mark.asyncio
async def test_accountability_service_detects_missed_plan_target_date():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="How is my housing plan looking?",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        plans=[
            {
                "id": "plan-housing",
                "plan_type": "housing",
                "title": "Move into my own place",
                "description": "Save enough to move out.",
                "priority": 5,
                "status": "active",
                "active": True,
                "target_date": "2026-05-01",
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "plan_drift"
    assert signals[0].metadata["subtype"] == "plan_target_missed"
    assert signals[0].metadata["days_overdue"] == 18


@pytest.mark.asyncio
async def test_accountability_service_detects_plan_progress_update():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I shipped the Rex voice pipeline improvements today.",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        plans=[
            {
                "id": "plan-rex-voice",
                "plan_type": "creative",
                "title": "Rex voice pipeline",
                "description": "Make Rex voice faster and more natural.",
                "priority": 3,
                "status": "active",
                "active": True,
            }
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "positive_follow_through"
    assert signals[0].metadata["subtype"] == "plan_progress"
    assert signals[0].metadata["matched_terms"] == [
        "pipeline",
        "rex",
        "voice",
    ]


@pytest.mark.asyncio
async def test_accountability_service_ignores_inactive_plans_and_closed_milestones():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="Review old plans.",
        time_context={"iso_timestamp": "2026-05-19T10:00:00-04:00"},
        plans=[
            {
                "id": "plan-old",
                "plan_type": "personal",
                "title": "Old plan",
                "priority": 5,
                "status": "archived",
                "active": True,
                "target_date": "2026-05-01",
            },
            {
                "id": "plan-active",
                "plan_type": "personal",
                "title": "Active plan",
                "priority": 3,
                "status": "active",
                "active": True,
            },
        ],
        plan_milestones=[
            {
                "id": "milestone-done",
                "plan_id": "plan-active",
                "title": "Closed milestone",
                "target_date": "2026-05-01",
                "status": "completed",
                "active": True,
            }
        ],
    )

    assert signals == []


@pytest.mark.asyncio
async def test_accountability_service_detects_repeated_delivery_pattern_from_memories():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I ordered DoorDash again tonight.",
        time_context={"iso_timestamp": "2026-05-19T20:00:00-04:00"},
        relevant_memories=[
            {
                "id": "memory-delivery-1",
                "memory_type": "event",
                "content": "I ordered DoorDash after work.",
                "active": True,
                "created_at": "2026-05-10T20:00:00-04:00",
            },
            {
                "id": "memory-delivery-2",
                "memory_type": "event",
                "content": "I used food delivery again instead of cooking.",
                "active": True,
                "created_at": "2026-05-14T20:00:00-04:00",
            },
        ],
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == "repeated_pattern"
    assert signal.metadata["category"] == "delivery_spending"
    assert signal.metadata["historical_occurrence_count"] == 2
    assert signal.metadata["occurrence_count"] == 3
    assert signal.metadata["source_counts"] == {
        "long_term_memory": 2,
        "entity_event": 0,
    }
    assert signal.source_refs[0].source_type == "long_term_memory"


@pytest.mark.asyncio
async def test_accountability_service_detects_repeated_transport_pattern_from_events():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I took Uber home again.",
        time_context={"iso_timestamp": "2026-05-19T20:00:00-04:00"},
        entity_events=[
            {
                "id": "event-uber-1",
                "event_type": "note",
                "title": "Uber after shift",
                "content": "User took Uber home after work.",
                "active": True,
                "occurred_at": "2026-05-12T22:00:00-04:00",
            },
            {
                "id": "event-uber-2",
                "event_type": "note",
                "title": "Rideshare repeat",
                "content": "User used a rideshare when tired.",
                "active": True,
                "occurred_at": "2026-05-16T22:00:00-04:00",
            },
        ],
    )

    assert len(signals) == 1
    assert signals[0].signal_type == "repeated_pattern"
    assert signals[0].metadata["category"] == "transport_spending"
    assert signals[0].metadata["source_counts"] == {
        "long_term_memory": 0,
        "entity_event": 2,
    }
    assert signals[0].source_refs[0].source_type == "entity_event"


@pytest.mark.asyncio
async def test_accountability_service_ignores_old_or_inactive_pattern_records():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="I got Starbucks again.",
        time_context={"iso_timestamp": "2026-05-19T20:00:00-04:00"},
        relevant_memories=[
            {
                "id": "memory-old-coffee",
                "memory_type": "event",
                "content": "I bought Starbucks.",
                "active": True,
                "created_at": "2026-03-01T09:00:00-04:00",
            },
            {
                "id": "memory-inactive-coffee",
                "memory_type": "event",
                "content": "I got coffee again.",
                "active": False,
                "created_at": "2026-05-10T09:00:00-04:00",
            },
        ],
        entity_events=[
            {
                "id": "event-old-coffee",
                "event_type": "note",
                "content": "User spent money at Dunkin.",
                "active": True,
                "occurred_at": "2026-03-01T09:00:00-04:00",
            }
        ],
    )

    assert signals == []


@pytest.mark.asyncio
async def test_accountability_service_requires_current_message_pattern_match():
    service = AccountabilityService()

    signals = await service.analyze_signals(
        message="What should I focus on today?",
        time_context={"iso_timestamp": "2026-05-19T20:00:00-04:00"},
        relevant_memories=[
            {
                "id": "memory-delivery-1",
                "memory_type": "event",
                "content": "I ordered DoorDash after work.",
                "active": True,
                "created_at": "2026-05-10T20:00:00-04:00",
            },
            {
                "id": "memory-delivery-2",
                "memory_type": "event",
                "content": "I used food delivery again instead of cooking.",
                "active": True,
                "created_at": "2026-05-14T20:00:00-04:00",
            },
        ],
    )

    assert signals == []
