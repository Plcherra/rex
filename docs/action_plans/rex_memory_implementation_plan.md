# Rex Memory Implementation Plan

## Strategy

This plan turns the Rex memory blueprint into a realistic implementation path for a solo developer working 2-3 hours per day.

The priority is not to build a perfect memory graph immediately. The priority is to make Rex reliable in daily use: corrections must replace stale truth, people must become first-class memory records, and plans must stay connected to the right people, dates, and commitments.

The phases are ordered to deliver value early. Phase 1 is intentionally small enough to complete in 1-2 days and directly targets the current `Al` vs `Melissa` failure mode.

## Phase 1 - Stabilize Explicit Corrections

**Priority:** High

**Goal:** Stop Rex from treating corrected information as an additional memory while the old wrong memory remains active.

**Key files to modify/create:**

- `backend/app/services/memory_extraction_service.py`
- `backend/app/services/memory_service.py`
- `tests/test_memory_extraction.py`
- `tests/test_memory_retrieval.py`
- Optional: `backend/supabase_schema.sql`

**Implementation scope:**

- Detect correction language like "not Al, Melissa", "that was wrong", "change X to Y".
- Update the best matching stale long-term memory when safe.
- Deactivate extra stale duplicates.
- Prefer corrected memories during retrieval.
- Add tests for person-name correction, location correction, and plan-detail correction.

**Success criteria:**

- A correction like "her name is Melissa, not Al" updates or deactivates stale `Al` memories.
- Rex no longer retrieves stale `Al` context as current truth after correction.
- Existing basic memory extraction still works.

**Rough time estimate:** 1-2 days

## Phase 2 - Add Correction Audit Trail

**Priority:** High

**Goal:** Make corrections inspectable and debuggable instead of hidden inside generic memory rows.

**Key files to modify/create:**

- `backend/supabase_schema.sql`
- `backend/app/models/memory.py`
- `backend/app/services/memory_service.py`
- `backend/app/services/memory_extraction_service.py`
- `tests/test_memory_extraction.py`

**Implementation scope:**

- Add a `memory_corrections` table.
- Add optional `superseded_by`, `confidence`, `correction_group`, and `metadata` fields to `long_term_memory`.
- Save each explicit correction with old value, new value, target hint, source message, and applied status.
- Keep this backend-only at first; no UI required yet.

**Success criteria:**

- Every applied correction leaves an audit row.
- Stale memories can point to their replacement or be marked inactive.
- Tests can prove a correction was detected and applied.

**Rough time estimate:** 2-3 days

## Phase 3 - Make People First-Class

**Priority:** High

**Goal:** Store people as `entities` records, not only as text inside facts or events.

**Key files to modify/create:**

- `backend/app/services/entity_service.py`
- `backend/app/services/memory_extraction_service.py`
- `backend/app/services/memory_service.py`
- `backend/app/models/entity.py`
- `tests/test_entity_service.py`
- `tests/test_memory_extraction.py`

**Implementation scope:**

- Improve person extraction from chat turns.
- Normalize names consistently.
- Add aliases like "girl from work", "my date", "coworker", when useful.
- Link entity events to people.
- Prevent duplicate people when the same person is mentioned repeatedly.

**Success criteria:**

- "Melissa" is stored as a person entity.
- Repeated mentions of Melissa update the same entity instead of creating duplicates.
- Entity events can explain what Rex knows about Melissa.

**Rough time estimate:** 3-5 days

## Phase 4 - Connect Corrections To People

**Priority:** High

**Goal:** When a correction names a person, update the person entity and related events instead of only updating a flat note.

**Key files to modify/create:**

- `backend/app/services/entity_service.py`
- `backend/app/services/memory_extraction_service.py`
- `backend/app/services/memory_service.py`
- `tests/test_entity_service.py`
- `tests/test_memory_extraction.py`
- `tests/test_memory_retrieval.py`

**Implementation scope:**

- If the user says "it is Melissa, not Al", resolve or create Melissa as the current person.
- Add "Al" as stale/wrong context only when useful for audit, not as an active alias.
- Add an entity event describing the correction.
- Deactivate or supersede entity events that incorrectly identify the person.

**Success criteria:**

- Asking "Do you remember Melissa?" returns the corrected person context.
- Asking about the old wrong name does not make Rex treat it as the current person.
- Corrections show up as entity events for traceability.

**Rough time estimate:** 3-5 days

## Phase 5 - Link Plans To People And Dates

**Priority:** High

**Goal:** Plans should reference the right person and update when the person, date, or desired outcome changes.

**Key files to modify/create:**

- `backend/supabase_schema.sql`
- `backend/app/models/plan.py`
- `backend/app/services/plan_service.py`
- `backend/app/services/entity_service.py`
- `backend/app/services/memory_extraction_service.py`
- `tests/test_plan_service.py`
- `tests/test_memory_extraction.py`

**Implementation scope:**

- Add or use `primary_entity_id` on plans.
- Link dating/work/personal plans to relevant entities.
- Update plan title, description, and desired outcome when corrected.
- Preserve milestones and commitments when a plan detail changes.

**Success criteria:**

- The dating plan links to Melissa, not only a text phrase.
- Correcting "Al" to "Melissa" updates the active dating plan.
- Rex can retrieve the plan through either "Melissa" or "my date next week".

**Rough time estimate:** 4-6 days

## Phase 6 - Improve Retrieval Ranking

**Priority:** High

**Goal:** Make prompt memory context choose the current, relevant, corrected records instead of noisy old records.

**Key files to modify/create:**

- `backend/app/services/memory_service.py`
- `backend/app/services/prompt_service.py`
- `backend/app/services/entity_service.py`
- `backend/app/services/plan_service.py`
- `tests/test_memory_retrieval.py`
- `tests/test_prompt_service.py`

**Implementation scope:**

- Add scoring for relevance, recency, importance, active status, and correction status.
- Penalize inactive or superseded records.
- Boost exact person, alias, rule, and plan matches.
- Boost recent explicit corrections.
- Cap prompt sections so memory does not bloat responses.

**Success criteria:**

- Prompt context includes Melissa when the user asks about the date plan.
- Prompt context includes Massachusetts/timezone when the user asks about time or location.
- Prompt context excludes stale active-looking `Al` rows after correction.

**Rough time estimate:** 4-6 days

## Phase 7 - Add Structured Memory UI Actions

**Priority:** Medium

**Goal:** Let the user inspect and correct structured memory from the app, not only from Supabase or chat.

**Key files to modify/create:**

- `lib/features/memory/data/memory_models.dart`
- `lib/features/memory/data/memory_api.dart`
- `lib/features/memory/application/memory_controller.dart`
- `lib/features/memory/presentation/pages/memory_page.dart`
- Backend route files if update/deactivate endpoints are missing for structured records

**Implementation scope:**

- Keep the layer tabs: Notes, People, Rules, Plans, Commitments.
- Add edit/deactivate actions for people, plans, rules, and commitments.
- Show aliases, linked plan/person IDs, status, and correction hints where useful.
- Avoid heavy UI; keep it founder-facing and practical.

**Success criteria:**

- The user can open Memory and see Melissa under People.
- The user can open Plans and see the dating plan linked to Melissa.
- The user can deactivate or edit an incorrect structured memory from the UI.

**Rough time estimate:** 4-7 days

## Phase 8 - Backfill Existing Real Memories

**Priority:** Medium

**Goal:** Convert obvious existing flat memories into structured people, plans, rules, and commitments without creating more noise.

**Key files to modify/create:**

- `backend/app/services/memory_extraction_service.py`
- `backend/app/services/entity_service.py`
- `backend/app/services/plan_service.py`
- Optional: `backend/scripts/backfill_structured_memory.py`
- `tests/test_memory_extraction.py`

**Implementation scope:**

- Add a safe one-time backfill script or service function.
- Read active long-term memories.
- Extract obvious person/plan/rule/commitment candidates.
- Skip ambiguous cases.
- Mark backfilled records with metadata.
- Do not delete original memories until the structured version is verified.

**Success criteria:**

- Existing memories like "I am in Massachusetts" and the dating plan become easier to retrieve.
- Backfill does not create duplicate people or duplicate plans.
- Backfill can be run locally or on the VPS intentionally, not automatically on every app start.

**Rough time estimate:** 3-5 days

## Phase 9 - Manual Daily-Use Validation

**Priority:** High

**Goal:** Prove the memory system works against real usage, not only tests.

**Key files to modify/create:**

- `docs/action_plans/rex_memory_manual_test.md`
- No code changes expected unless bugs are found

**Implementation scope:**

- Create a short manual test checklist.
- Test one person correction.
- Test one location/timezone question.
- Test one active plan with a person and date.
- Test one rule and one accountability signal.
- Check Memory UI layers.
- Check Supabase rows for stale active records.

**Success criteria:**

- Rex remembers the corrected person.
- Rex does not keep repeating stale wrong names.
- Rex knows the user's timezone/location context when relevant.
- Rex retrieves the right plan and related commitments.
- Manual test results are documented.

**Rough time estimate:** 1-2 days

## Phase 10 - Add Guardrails And Regression Tests

**Priority:** Medium

**Goal:** Prevent future memory regressions as voice, accountability, and structured memory continue growing.

**Key files to modify/create:**

- `tests/test_memory_extraction.py`
- `tests/test_memory_retrieval.py`
- `tests/test_prompt_service.py`
- `tests/test_entity_service.py`
- `tests/test_plan_service.py`
- Optional: `docs/action_plans/rex_memory_regression_cases.md`

**Implementation scope:**

- Add regression cases for stale corrections.
- Add prompt-context tests for people, plans, location, and rules.
- Add duplicate prevention tests.
- Add tests for inactive/superseded memory exclusion.
- Document the top real-world failure cases.

**Success criteria:**

- A future change cannot reintroduce the `Al` vs `Melissa` failure without tests failing.
- Tests cover correction, entity resolution, plan linking, and retrieval.
- Full validation remains fast enough for local development.

**Rough time estimate:** 2-4 days

## Recommended Build Order

1. Phase 1
2. Phase 3
3. Phase 4
4. Phase 5
5. Phase 6
6. Phase 9
7. Phase 2
8. Phase 7
9. Phase 8
10. Phase 10

Phase 2 is useful, but it can follow the first correction fix if time is tight. The fastest path to daily value is: fix corrections, make people real, link plans, then improve retrieval.
