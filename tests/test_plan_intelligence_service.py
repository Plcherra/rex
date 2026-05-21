from app.models.memory_discipline import MemoryDisciplineAction
from app.services.plan_intelligence_service import PlanIntelligenceService


def test_income_target_routes_under_relocation_plan_as_milestone():
    service = PlanIntelligenceService()
    candidate = {
        "plan_type": "finance",
        "title": "Reach $5k monthly income",
        "description": "Build location-independent income from client work.",
        "desired_outcome": "Move to Europe with stable remote income.",
        "priority": 5,
    }
    context = {
        "active_plans": [
            {
                "id": "plan-europe",
                "plan_type": "personal",
                "title": "Relocate to Europe next year",
                "description": "Build location independent income and savings.",
                "priority": 5,
                "active": True,
            }
        ],
        "active_milestones": [],
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.CREATE_MILESTONE
    assert decision.parent_plan_id == "plan-europe"
    assert decision.payload["plan_id"] == "plan-europe"
    assert decision.payload["title"] == "Reach $5k monthly income"


def test_app_launch_goal_routes_under_app_development_plan():
    service = PlanIntelligenceService()
    candidate = {
        "plan_type": "career",
        "title": "Launch EchoDesk and FlowForce for revenue",
        "description": "Ship app MVPs and use them to win clients.",
        "desired_outcome": "Generate monthly revenue from shipped apps.",
        "priority": 4,
    }
    context = {
        "active_plans": [
            {
                "id": "plan-apps",
                "plan_type": "career",
                "title": "Three-month app development plan",
                "description": "Prioritize building and shipping apps, Rex polishing, and project revenue.",
                "priority": 5,
                "active": True,
            }
        ],
        "active_milestones": [],
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.CREATE_MILESTONE
    assert decision.payload["plan_id"] == "plan-apps"
    assert decision.payload["metadata"]["plan_intelligence_version"] == 1


def test_immigration_variants_route_under_existing_europe_plan():
    service = PlanIntelligenceService()
    context = {
        "active_plans": [
            {
                "id": "plan-europe",
                "plan_type": "personal",
                "title": "Relocate to Europe next year",
                "description": "Leave the USA next year to live in Europe and visit Greece.",
                "desired_outcome": "Successfully living in Europe.",
                "priority": 5,
                "active": True,
            },
            {
                "id": "plan-apps",
                "plan_type": "career",
                "title": "Three-month app development plan",
                "description": "Prioritize building and shipping EchoDesk, FlowForce, and Rex.",
                "priority": 5,
                "active": True,
            },
        ],
        "active_milestones": [],
    }
    candidate = {
        "plan_type": "immigration",
        "title": "Estonia e-residency application",
        "description": "Apply for Estonia e-residency using EchoDesk to establish EU business presence.",
        "desired_outcome": "Successful approval enabling EU business operations.",
        "priority": 5,
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.CREATE_MILESTONE
    assert decision.parent_plan_id == "plan-europe"


def test_single_app_variants_route_under_app_development_plan():
    service = PlanIntelligenceService()
    context = {
        "active_plans": [
            {
                "id": "plan-europe",
                "plan_type": "personal",
                "title": "Relocate to Europe next year",
                "description": "Leave the USA next year to live in Europe.",
                "priority": 5,
                "active": True,
            },
            {
                "id": "plan-apps",
                "plan_type": "career",
                "title": "Three-month app development plan",
                "description": "Prioritize building and shipping EchoDesk, FlowForce, and Rex polishing to generate revenue.",
                "priority": 5,
                "active": True,
            },
        ],
        "active_milestones": [],
    }
    candidate = {
        "plan_type": "creative",
        "title": "Build and launch FlowForce app",
        "description": "Develop an operations app for small businesses.",
        "desired_outcome": "Create a product that gains customers through better workflows.",
        "priority": 4,
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.CREATE_MILESTONE
    assert decision.parent_plan_id == "plan-apps"


def test_crowded_active_plan_list_blocks_automatic_top_level_creation():
    service = PlanIntelligenceService()
    context = {
        "active_plans": [
            {
                "id": f"plan-{index}",
                "plan_type": "personal",
                "title": f"Existing major plan {index}",
                "description": "Existing durable area.",
                "priority": 4,
                "active": True,
            }
            for index in range(5)
        ],
        "active_milestones": [],
    }
    candidate = {
        "plan_type": "health",
        "title": "Build a consistent strength training routine",
        "description": "Lift three times per week and track progression.",
        "desired_outcome": "Gain strength and maintain energy while coding.",
        "priority": 4,
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.ASK_CONFIRMATION
    assert decision.requires_confirmation is True


def test_dating_logistics_route_as_commitment_under_existing_person_plan():
    service = PlanIntelligenceService()
    candidate = {
        "plan_type": "dating",
        "title": "Confirm Monday dinner time with Melissa",
        "description": "Text Melissa to lock the exact day, time, and restaurant.",
        "desired_outcome": "Have the date details confirmed.",
        "primary_entity_id": "person-melissa",
        "priority": 4,
    }
    context = {
        "active_plans": [
            {
                "id": "plan-melissa",
                "plan_type": "dating",
                "title": "Ask Melissa out for dinner",
                "description": "Plan the next-week date with Melissa.",
                "primary_entity_id": "person-melissa",
                "priority": 4,
                "active": True,
            }
        ],
        "active_milestones": [
            {
                "id": "milestone-details",
                "plan_id": "plan-melissa",
                "title": "Lock date details",
                "description": "Confirm day, time, and restaurant.",
                "active": True,
            }
        ],
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.CREATE_COMMITMENT
    assert decision.payload["plan_id"] == "plan-melissa"
    assert decision.payload["milestone_id"] == "milestone-details"
    assert decision.payload["commitment_type"] == "relationship"


def test_unrelated_durable_health_goal_can_create_top_level_plan():
    service = PlanIntelligenceService()
    candidate = {
        "plan_type": "health",
        "title": "Build a consistent strength training routine",
        "description": "Lift three times per week and track progression.",
        "desired_outcome": "Gain strength and maintain energy while coding.",
        "priority": 4,
    }
    context = {
        "active_plans": [
            {
                "id": "plan-europe",
                "plan_type": "personal",
                "title": "Relocate to Europe next year",
                "description": "Build location independent income.",
                "priority": 5,
                "active": True,
            }
        ],
        "active_milestones": [],
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.CREATE_PLAN
    assert decision.payload["title"] == "Build a consistent strength training routine"


def test_recursive_parent_plan_candidate_updates_description_not_milestone():
    service = PlanIntelligenceService()
    context = {
        "active_plans": [
            {
                "id": "plan-move",
                "plan_type": "immigration",
                "title": "Move out of the country next year",
                "description": "Move abroad after reaching stable income.",
                "desired_outcome": "Live outside the USA with stable remote income.",
                "priority": 5,
                "active": True,
            }
        ],
        "active_milestones": [],
    }
    candidate = {
        "plan_type": "immigration",
        "title": "Move out of the country next year",
        "description": "Primary route is Italian citizenship, with Portugal D7 as backup.",
        "desired_outcome": "Portugal or Italy route clarified.",
        "priority": 5,
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.UPDATE_PLAN
    assert decision.parent_plan_id == "plan-move"
    assert "Italian citizenship" in decision.payload["description"]


def test_duplicate_income_target_updates_existing_milestone():
    service = PlanIntelligenceService()
    context = {
        "active_plans": [
            {
                "id": "plan-move",
                "plan_type": "immigration",
                "title": "Move out of the country next year",
                "description": "Move after reaching income targets.",
                "priority": 5,
                "active": True,
            }
        ],
        "active_milestones": [
            {
                "id": "milestone-income",
                "plan_id": "plan-move",
                "title": "Reach $5k monthly income",
                "description": "Reach stable monthly income before leaving.",
                "status": "open",
                "active": True,
            }
        ],
    }
    candidate = {
        "plan_type": "finance",
        "title": "$5k monthly revenue target",
        "description": "Hit $5k/month in income before moving.",
        "priority": 5,
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.UPDATE_MILESTONE
    assert decision.target_milestone_id == "milestone-income"


def test_first_million_exploration_is_ignored_not_milestone():
    service = PlanIntelligenceService()
    context = {
        "active_plans": [
            {
                "id": "plan-move",
                "plan_type": "immigration",
                "title": "Move out of the country next year",
                "description": "Move after reaching income targets.",
                "priority": 5,
                "active": True,
            }
        ],
        "active_milestones": [],
    }
    candidate = {
        "plan_type": "finance",
        "title": "Reach first million",
        "description": "User asked how long it would take to reach the first million.",
        "priority": 3,
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.IGNORE_NOISY_CANDIDATE


def test_historical_person_context_routes_to_entity_event_when_entity_known():
    service = PlanIntelligenceService()
    context = {
        "active_plans": [
            {
                "id": "plan-melissa",
                "plan_type": "dating",
                "title": "Ask Melissa out for dinner",
                "description": "One active dating follow-up plan with Melissa.",
                "primary_entity_id": "entity-melissa",
                "priority": 4,
                "active": True,
            }
        ],
        "active_milestones": [],
    }
    candidate = {
        "plan_type": "dating",
        "title": "Melissa said she would let me know",
        "description": "Melissa said she would let me know as her response.",
        "primary_entity_id": "entity-melissa",
        "priority": 4,
    }

    decision = service.classify_plan_candidate(candidate, context)

    assert decision.action == MemoryDisciplineAction.CREATE_ENTITY_EVENT
    assert decision.payload["entity_id"] == "entity-melissa"
