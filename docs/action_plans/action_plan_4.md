# Action Plan 4 - Accountability and Pattern Recognition

## Goal
Make Rex actively compare current behavior against past rules, commitments, and plans.

## Why This Matters (Personal Context)
This is the phase where Rex becomes a true accountability partner. The founder wants Rex to notice patterns like “you said you would cut DoorDash last month and here you are again,” remember promises (“I’ll work out tomorrow morning”), track multi-month plans (income targets to move out of the country, immigration timelines), and gently but directly call out violations of personal rules (no Uber, only Bom Dough coffee, grocery caps, rent rules). This transforms Rex from a passive memory store into an active, honest co-pilot that helps the founder actually change behavior.

## Key Deliverables
- Rule violation detection for money/transport/food delivery/coffee/rent categories
- Commitment tracking and missed-commitment retrieval
- Plan progress prompts and weekly/monthly review logic
- “Why Rex is bringing this up” metadata
- Flutter UI sections for rules, commitments, and plans

## Estimated Time
1-2 weeks (solo founder pace)

## Dependencies
Action Plan 3 (Entity, Rule, and Plan Memory Schema) must be 100% complete.

## Checklist (10 Actionable Steps)

1. [ ] **Define accountability signal types and metadata**
   - Exact files to create or modify: `backend/app/models/accountability.py`, `backend/app/services/accountability_service.py`, optionally `backend/supabase_schema.sql`
   - What must be implemented: Define the core accountability concepts Rex can detect: rule violation, missed commitment, plan drift, repeated pattern, upcoming deadline, budget risk, and positive follow-through. Include metadata for why the signal was generated, which source records caused it, confidence, severity, and suggested prompt wording.
   - Success criteria: Accountability signals have a stable model that can be returned from services, injected into prompts, and eventually shown in Flutter without guessing at raw memory text.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add accountability signal models`
   - Rough time estimate: 3-4 hours

2. [ ] **Create the backend `AccountabilityService` skeleton**
   - Exact files to create or modify: `backend/app/services/accountability_service.py`, `backend/app/dependencies.py`
   - What must be implemented: Add a service that accepts the current user message, current time context, active personal rules, open commitments, active plans, recent entity events, and relevant memories, then returns a list of accountability signals.
   - Success criteria: The service is dependency-injectable, testable without Grok or Supabase, and does not change existing chat behavior until prompt integration is added.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add accountability service skeleton`
   - Rough time estimate: 3-5 hours

3. [ ] **Implement personal rule violation detection**
   - Exact files to create or modify: `backend/app/services/accountability_service.py`, `backend/app/services/rule_service.py`, `tests/test_accountability_service.py`
   - What must be implemented: Detect likely violations of active personal rules from the current message and recent context. Start with simple rule categories for transport, delivery food, coffee, groceries, rent, subscriptions, and spending caps.
   - Success criteria: Messages like “I ordered DoorDash again” or “I took Uber home” can trigger a structured rule-violation signal when matching active rules exist, while unrelated mentions do not create false positives.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_accountability_service.py`
   - Suggested git commit message: `feat: detect personal rule violations`
   - Rough time estimate: 5-8 hours

4. [ ] **Implement commitment tracking and missed-commitment logic**
   - Exact files to create or modify: `backend/app/services/accountability_service.py`, `backend/app/services/commitment_service.py`, `backend/app/services/time_context_service.py`, `tests/test_accountability_service.py`
   - What must be implemented: Compare open commitments against current time and the user’s latest message. Detect missed commitments, due-today commitments, completed commitments, and commitments that need follow-up.
   - Success criteria: Rex can identify practical cases like “I’ll work out tomorrow morning” becoming overdue the next afternoon, and can mark or suggest completion when the user reports follow-through.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_accountability_service.py`
   - Suggested git commit message: `feat: detect missed commitments`
   - Rough time estimate: 5-8 hours

5. [ ] **Implement plan progress and deadline drift logic**
   - Exact files to create or modify: `backend/app/services/accountability_service.py`, `backend/app/services/plan_service.py`, `backend/app/services/time_context_service.py`, `tests/test_accountability_service.py`
   - What must be implemented: Compare active plans and milestones against current time, target dates, status, and recent updates. Generate signals for upcoming milestones, overdue milestones, stalled plans, and progress updates.
   - Success criteria: Rex can surface context like “your move-out income target is 6 weeks away and this update affects it” without the founder manually re-explaining the plan.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_accountability_service.py`
   - Suggested git commit message: `feat: add plan progress accountability`
   - Rough time estimate: 5-9 hours

6. [ ] **Add repeated-pattern detection from recent events and memories**
   - Exact files to create or modify: `backend/app/services/accountability_service.py`, `backend/app/services/memory_service.py`, `backend/app/services/entity_service.py`, `tests/test_accountability_service.py`
   - What must be implemented: Detect repeated behavior patterns from recent memories, entity events, rules, and commitments. Start with simple keyword/category counts over a configurable lookback window before adding heavier semantic logic.
   - Success criteria: Rex can identify repeated behavior like recurring delivery spending, repeated Uber use, repeated missed workouts, or repeated dating-context anxiety when enough recent evidence exists.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_accountability_service.py`
   - Suggested git commit message: `feat: detect recurring accountability patterns`
   - Rough time estimate: 6-10 hours

7. [ ] **Inject accountability signals into prompts**
   - Exact files to create or modify: `backend/app/services/prompt_service.py`, `backend/app/services/chat_service.py`, `backend/app/services/accountability_service.py`, `tests/test_prompt_service.py`
   - What must be implemented: Call `AccountabilityService` during chat orchestration and add a compact accountability section to the Grok prompt with signal type, severity, reason, source age, and suggested framing. Keep the final response natural and direct, not robotic.
   - Success criteria: Accountability context appears in both streaming and non-streaming chat prompts, stays under prompt budget, and existing memory/context sections remain backward compatible.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: inject accountability context into prompts`
   - Rough time estimate: 4-7 hours

8. [ ] **Expose accountability data through backend routes**
   - Exact files to create or modify: `backend/app/routes/accountability.py`, `backend/app/main.py`, `backend/app/models/accountability.py`, `tests/test_accountability_routes.py`
   - What must be implemented: Add private founder-focused endpoints for listing current accountability signals, open commitments, active rule risks, plan risks, and recent pattern detections. Include filters for active, dismissed, severity, and source type if useful.
   - Success criteria: Flutter can fetch accountability context without scraping chat messages, and route tests cover success, empty, validation, and service-error paths without real Grok or Supabase calls.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_accountability_routes.py`
   - Suggested git commit message: `feat: add accountability routes`
   - Rough time estimate: 5-8 hours

9. [ ] **Build Flutter UI sections for rules, commitments, and plans**
   - Exact files to create or modify: `lib/features/accountability/data/accountability_api.dart`, `lib/features/accountability/data/accountability_models.dart`, `lib/features/accountability/application/accountability_controller.dart`, `lib/features/accountability/presentation/pages/accountability_page.dart`, `lib/features/chat/presentation/pages/chat_page.dart`, `lib/core/providers.dart`
   - What must be implemented: Add a clean founder-facing accountability page showing active rules, open commitments, plan progress, and recent signals. Add navigation from the chat screen without disrupting the current chat and memory flows.
   - Success criteria: The user can see what Rex is tracking, why it matters, and which rules/commitments/plans need attention. Empty, loading, and error states are handled cleanly.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add accountability ui`
   - Rough time estimate: 1-2 days

10. [ ] **Run full validation and manual accountability test**
    - Exact files to create or modify: No code changes expected unless validation exposes bugs
    - What must be implemented: Run full backend and Flutter validation, then manually test a realistic accountability flow: create personal rules, create a commitment, create a multi-month plan, send messages that violate or update them, and verify Rex brings up the right context naturally.
    - Success criteria: Backend tests pass, Flutter tests pass, existing chat/memory behavior remains backward compatible, and Rex can call out at least one rule violation, one missed commitment, and one plan-progress issue with clear “why this came up” metadata.
    - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
    - Suggested git commit message: `test: validate accountability system`
    - Rough time estimate: 4-6 hours

## Revision History
- 2026-05-12 - Action Plan 4 created from Alignment Plan and updated REX_VISION.md
