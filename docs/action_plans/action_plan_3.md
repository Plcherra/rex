# Action Plan 3 - Entity, Rule, and Plan Memory Schema

## Goal
Move beyond generic long-term memory into structured founder life memory.

## Why This Matters (Personal Context)
This phase turns Rex from a simple memory store into a true understanding of the founder’s real life. It will allow Rex to remember specific people (like Clara or Melissa), track personal rules (no Uber, only Bom Dough coffee, grocery caps), maintain multi-month plans (income targets to move out of the country, immigration timelines), and connect new updates to existing context without the founder having to re-explain everything. This is what enables real accountability and long-term co-pilot behavior.

## Key Deliverables
- Extend Supabase schema with `entities`, `entity_events`, `personal_rules`, `plans`, `plan_milestones`, and possibly `commitments`
- Add backend models/routes/services/repositories for these records
- Update memory extraction prompt to emit entity/rule/plan candidates
- Add retrieval that detects names like Clara/Melissa and pulls entity timeline context
- Add tests for extraction, deduplication, and retrieval

## Estimated Time
5-10 focused days (solo founder pace)

## Dependencies
Action Plan 1 (Time-Aware Prompt Foundation) must be complete. Existing Supabase memory service and PromptService from previous plans.

## Checklist (10 Actionable Steps)

1. [x] **Design the structured memory schema**
   - Exact files to create or modify: `backend/supabase_schema.sql`, optionally `docs/memory_retrieval.md`
   - What must be implemented: Add schema definitions for `entities`, `entity_events`, `personal_rules`, `plans`, `plan_milestones`, and `commitments`. Include UUID primary keys, timestamps, active/status fields, importance/priority fields where useful, and foreign keys back to conversations, messages, or long-term memory where appropriate.
   - Success criteria: Schema is backward compatible with existing `conversations`, `messages`, and `long_term_memory`; no existing table or column is removed; all new tables can be created safely in a fresh Supabase project.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add structured memory schema`
   - Rough time estimate: 3-5 hours

2. [x] **Create backend models for structured memory records**
   - Exact files to create or modify: `backend/app/models/entity.py`, `backend/app/models/personal_rule.py`, `backend/app/models/plan.py`, `backend/app/models/commitment.py`, optionally `backend/app/models/memory.py`
   - What must be implemented: Define Pydantic request/response models for entities, entity events, personal rules, plans, plan milestones, and commitments. Include clear enums or literal types for categories such as person, job, place, rule, finance, dating, immigration, health, goal, and deadline.
   - Success criteria: Models validate required fields, optional metadata, timestamps, statuses, and IDs consistently with the existing backend model style.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add structured memory models`
   - Rough time estimate: 3-4 hours

3. [x] **Add repository methods for Supabase structured memory access**
   - Exact files to create or modify: `backend/app/services/memory_service.py`, optionally new files under `backend/app/repositories/` if the project introduces a repository layer
   - What must be implemented: Add async Supabase read/write/update/deactivate helpers for entities, entity events, personal rules, plans, plan milestones, and commitments. Keep the existing `long_term_memory` methods working unchanged.
   - Success criteria: All new storage methods use the shared async HTTP client pattern, never call real Supabase in tests, and expose narrow methods that services can reuse without duplicating REST request code.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add structured memory repositories`
   - Rough time estimate: 5-8 hours

4. [x] **Add service-level APIs for entities, rules, plans, and commitments**
   - Exact files to create or modify: `backend/app/services/entity_service.py`, `backend/app/services/rule_service.py`, `backend/app/services/plan_service.py`, `backend/app/services/commitment_service.py`, `backend/app/dependencies.py`
   - What must be implemented: Create business-logic services for creating, updating, deactivating, deduplicating, and retrieving structured memory records. Services should hide Supabase details from routes and prompt assembly.
   - Success criteria: Each service has a small public API, handles not-found and validation errors cleanly, and can be dependency-injected in route tests.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add structured memory services`
   - Rough time estimate: 6-10 hours

5. [x] **Create backend routes for structured memory management**
   - Exact files to create or modify: `backend/app/routes/entities.py`, `backend/app/routes/rules.py`, `backend/app/routes/plans.py`, `backend/app/routes/commitments.py`, `backend/app/main.py`
   - What must be implemented: Add CRUD-style endpoints for listing, creating, updating, and deactivating entities, personal rules, plans, plan milestones, and commitments. Keep endpoints private/simple for founder dogfooding; do not add public product complexity yet.
   - Success criteria: Routes use dependency injection, normalized error handling, and response models. Existing `/memory`, `/chat`, and `/conversations` routes remain backward compatible.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add structured memory routes`
   - Rough time estimate: 5-8 hours

6. [x] **Update Grok memory extraction for structured candidates**
   - Exact files to create or modify: `backend/app/services/memory_extraction_service.py`, `backend/app/services/prompt_service.py`, `tests/test_memory_extraction.py`
   - What must be implemented: Extend the extraction prompt and parser so Grok can emit structured candidates for entities, entity events, personal rules, plans, plan milestones, and commitments while still supporting existing `fact`, `preference`, and `event` memories.
   - Success criteria: Extraction remains optional and non-blocking, rejects malformed JSON safely, filters low-value candidates, and does not break existing long-term memory extraction tests.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_memory_extraction.py`
   - Suggested git commit message: `feat: extract structured memory candidates`
   - Rough time estimate: 5-8 hours

7. [x] **Implement deduplication and linking logic**
   - Exact files to create or modify: `backend/app/services/entity_service.py`, `backend/app/services/rule_service.py`, `backend/app/services/plan_service.py`, `backend/app/services/commitment_service.py`, `backend/app/services/memory_extraction_service.py`
   - What must be implemented: Add simple but reliable deduplication for repeated people, aliases, rules, plans, and commitments. Link new entity events to existing entities when names or aliases match. Link extracted records back to source conversation/message IDs when available.
   - Success criteria: Repeated mentions like “Clara,” “the girl Clara,” and “Clara from work” do not create endless duplicate entities, and repeated rules update or reinforce existing rules instead of creating noise.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: deduplicate structured memories`
   - Rough time estimate: 5-9 hours

8. [x] **Add structured retrieval for prompt context**
   - Exact files to create or modify: `backend/app/services/memory_service.py`, `backend/app/services/prompt_service.py`, `backend/app/services/entity_service.py`, `backend/app/services/rule_service.py`, `backend/app/services/plan_service.py`
   - What must be implemented: Retrieve relevant entities, recent entity events, active personal rules, active plans, upcoming milestones, and open commitments for each chat turn. Use the current user message, detected names, keywords, importance, recency, and plan/rule status to choose what enters the prompt.
   - Success criteria: If the user mentions a known person, rule, or plan, Rex receives the correct structured context without overloading the prompt. Existing generic long-term memory retrieval still works as fallback.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: retrieve structured memory context`
   - Rough time estimate: 6-10 hours

9. [x] **Add comprehensive backend tests**
   - Exact files to create or modify: `tests/test_entity_service.py`, `tests/test_rule_service.py`, `tests/test_plan_service.py`, `tests/test_structured_memory_routes.py`, update `tests/test_prompt_service.py` and `tests/test_memory_extraction.py`
   - What must be implemented: Add tests for schema-shaped payloads, create/update/deactivate flows, extraction parsing, deduplication, retrieval by name, retrieval by active rule/plan, and prompt context injection.
   - Success criteria: Tests cover the main success and failure paths without calling real Grok or Supabase. Future regressions in entity/rule/plan memory should fail fast.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `test: cover structured memory system`
   - Rough time estimate: 6-10 hours

10. [ ] **Run full validation and manual structured-memory test**
    - Exact files to create or modify: No code changes expected unless validation exposes bugs
    - What must be implemented: Run the full backend suite, then manually test a realistic flow: mention a person, create a rule, describe a plan with a deadline, return later with a related message, and verify the prompt includes the relevant entity/rule/plan context.
    - Success criteria: Full backend tests pass, existing chat/memory behavior remains backward compatible, structured memories are saved correctly, and Rex can connect a new message to prior people, rules, and plans.
    - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
    - Suggested git commit message: `test: validate structured memory foundation`
    - Rough time estimate: 2-4 hours

## Revision History
- 2026-05-12 - Action Plan 3 created from Alignment Plan and updated REX_VISION.md
