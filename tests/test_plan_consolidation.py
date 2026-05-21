import pytest

from backend.scripts.consolidate_plans import (
    build_plan_clusters,
    consolidate_plans,
)


class FakeConsolidationMemoryService:
    def __init__(self):
        self.plans = []
        self.milestones = []

    async def list_plans(self, limit=200, plan_type=None, status=None, active=None):
        rows = self.plans
        if plan_type is not None:
            rows = [row for row in rows if row.get("plan_type") == plan_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active", True) is active]
        return rows[:limit]

    async def update_plan(self, plan_id, **updates):
        for plan in self.plans:
            if plan["id"] == plan_id:
                plan.update(updates)
                return plan
        return None

    async def list_plan_milestones(
        self,
        limit=500,
        plan_id=None,
        status=None,
        active=None,
    ):
        rows = self.milestones
        if plan_id is not None:
            rows = [row for row in rows if row.get("plan_id") == plan_id]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active", True) is active]
        return rows[:limit]

    async def create_plan_milestone(self, payload):
        row = {"id": f"milestone-{len(self.milestones) + 1}", **payload}
        self.milestones.append(row)
        return row


def _plan(
    plan_id,
    title,
    plan_type,
    *,
    description=None,
    desired_outcome=None,
    priority=4,
    primary_entity_id=None,
):
    return {
        "id": plan_id,
        "title": title,
        "plan_type": plan_type,
        "description": description,
        "desired_outcome": desired_outcome,
        "primary_entity_id": primary_entity_id,
        "priority": priority,
        "status": "active",
        "active": True,
        "metadata": {},
    }


def test_build_plan_clusters_groups_duplicate_melissa_date_plans():
    clusters = build_plan_clusters(
        [
            _plan(
                "plan-1",
                "Date with Melissa next week",
                "dating",
                primary_entity_id="entity-melissa",
                priority=4,
            ),
            _plan(
                "plan-2",
                "Monday date with Melissa",
                "dating",
                description="Go on the planned date with Melissa outside of work.",
                primary_entity_id=None,
                priority=4,
            ),
        ]
    )

    assert len(clusters) == 1
    assert clusters[0].name == "dating_person_melissa"
    assert clusters[0].keep["id"] in {"plan-1", "plan-2"}
    assert len(clusters[0].archive) == 1


def test_build_plan_clusters_ignores_capitalized_non_name_words():
    clusters = build_plan_clusters(
        [
            _plan(
                "plan-1",
                "Ask Melissa out for dinner",
                "dating",
                description="I invited Melissa today in a teasing way.",
                desired_outcome="Successful date with Melissa",
                priority=4,
            ),
            _plan(
                "plan-2",
                "Monday outing with Melissa",
                "dating",
                description=(
                    "Pursuing a date or meetup with Melissa this Monday; "
                    "follow-up opportunity on Thursday to confirm."
                ),
                desired_outcome="Clear confirmation or successful one-on-one time",
                priority=4,
            ),
        ]
    )

    assert len(clusters) == 1
    assert clusters[0].name == "dating_person_melissa"
    assert clusters[0].archive[0]["id"] in {"plan-1", "plan-2"}


def test_build_plan_clusters_groups_immigration_variants_under_europe_root():
    clusters = build_plan_clusters(
        [
            _plan(
                "plan-europe",
                "Relocate to Europe next year",
                "personal",
                description="Leave the USA next year to live in Europe.",
                priority=5,
            ),
            _plan(
                "plan-estonia",
                "Estonia e-residency application",
                "immigration",
                description="Apply for Estonia e-residency to establish EU business presence.",
                priority=5,
            ),
            _plan(
                "plan-italy",
                "European relocation via Italian citizenship",
                "immigration",
                description="Pursue Italian citizenship while preparing the physical move to Europe.",
                priority=5,
            ),
        ]
    )

    income_cluster = next(
        cluster for cluster in clusters if cluster.name == "life_freedom_income"
    )
    assert income_cluster.keep["id"] == "plan-europe"
    assert {plan["id"] for plan in income_cluster.archive} == {
        "plan-estonia",
        "plan-italy",
    }


def test_build_plan_clusters_groups_personal_rex_launch_under_app_root():
    clusters = build_plan_clusters(
        [
            _plan(
                "plan-apps",
                "Three-month app development plan",
                "career",
                description="Prioritize building and shipping EchoDesk, FlowForce, and Rex.",
                priority=5,
            ),
            _plan(
                "plan-rex",
                "Launch Rex Melissa",
                "personal",
                description="Polish Rex for first usable version and external testing.",
                priority=5,
            ),
        ]
    )

    app_cluster = next(
        cluster for cluster in clusters if cluster.name == "app_development_roadmap"
    )
    assert app_cluster.keep["id"] == "plan-apps"
    assert [plan["id"] for plan in app_cluster.archive] == ["plan-rex"]


@pytest.mark.asyncio
async def test_consolidate_plans_dry_run_does_not_write():
    memory = FakeConsolidationMemoryService()
    memory.plans.extend(
        [
            _plan("plan-europe", "Relocate to Europe next year", "personal", priority=5),
            _plan(
                "plan-income",
                "Reach 5k monthly income in 12 months",
                "career",
                description="Build remote income from projects.",
                priority=5,
            ),
        ]
    )

    report = await consolidate_plans(memory, apply=False)

    assert report.scanned == 2
    assert report.clusters[0]["name"] == "life_freedom_income"
    assert report.archived == []
    assert memory.milestones == []
    assert all(plan["active"] is True for plan in memory.plans)


@pytest.mark.asyncio
async def test_consolidate_plans_archives_duplicates_and_merges_non_milestone_details():
    memory = FakeConsolidationMemoryService()
    memory.plans.extend(
        [
            _plan(
                "plan-root",
                "Date with Melissa next week",
                "dating",
                desired_outcome="Successful date with locked-in details.",
                priority=4,
            ),
            _plan(
                "plan-duplicate",
                "Monday date with Melissa",
                "dating",
                description="Go on the planned date with Melissa outside of work.",
                priority=4,
            ),
        ]
    )

    report = await consolidate_plans(memory, apply=True)

    assert report.errors == []
    assert len(report.archived) == 1
    archived = next(plan for plan in memory.plans if plan["id"] == "plan-duplicate")
    assert archived["active"] is False
    assert archived["status"] == "archived"
    assert archived["metadata"]["cleanup_reason"] == "plan_consolidation"
    assert archived["metadata"]["consolidated_into_plan_id"] == "plan-root"
    assert memory.milestones == []
    assert len(report.plans_updated) == 1
    root = next(plan for plan in memory.plans if plan["id"] == "plan-root")
    assert "Monday date with Melissa" in root["description"]


@pytest.mark.asyncio
async def test_consolidate_plans_still_creates_badge_like_milestones():
    memory = FakeConsolidationMemoryService()
    memory.plans.extend(
        [
            _plan(
                "plan-root",
                "Relocate to Europe next year",
                "personal",
                description="Move after reaching stable income.",
                priority=5,
            ),
            _plan(
                "plan-income",
                "Reach $5k monthly income",
                "finance",
                description="Reach stable monthly income before moving.",
                priority=5,
            ),
        ]
    )

    report = await consolidate_plans(memory, apply=True)

    assert report.errors == []
    assert len(memory.milestones) == 1
    assert memory.milestones[0]["title"] == "Reach $5k monthly income"
    assert memory.milestones[0]["metadata"]["consolidated_from_plan_id"] == "plan-income"
