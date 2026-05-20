# Rex Brain System - Full Implementation Plan

## Overview

The Rex Brain System is the permanent memory intelligence layer for Rex. Its job is to keep long-term memory, structured memory, plans, rules, commitments, and entities clean by default.

This is not a one-time cleanup. It becomes the standard behavior before any structured memory is saved or updated.

### Core Philosophy

- Quality and clarity over quantity.
- Prefer updating, merging, or attaching details to existing structures before creating anything new.
- Treat duplication, fragmentation, and stale names as memory quality bugs.
- Corrections from the user are high-priority instructions and should be applied immediately.
- Keep the Accountability screen usable: few top-level plans, clear milestones, and concrete tasks.

### Target End State

Rex follows this hierarchy:

1. Top-level plan: a durable life/work area that lasts weeks or months.
2. Milestones: meaningful checkpoints or sub-goals inside the plan.
3. Tasks/checklist items: concrete next actions, commitments, or small steps.
4. Entity links: people, projects, places, organizations, and topics attached to the right plan/milestone/task.

Rex should usually have only 2-5 active top-level plans unless the user truly has more distinct life areas.

### Global 5-Step Discipline Process

1. **Listen and Detect**
   - Classify the incoming user statement as one or more of:
     - new fact
     - correction
     - plan update
     - new plan candidate
     - milestone candidate
     - task/commitment candidate
     - rule update
     - entity update

2. **Check Existing Memory**
   - Retrieve related active plans, milestones, commitments, rules, and entities.
   - Include close title/name matches, aliases, primary entity links, source memory links, and semantic keyword overlap.

3. **Decide Action**
   - Correction: archive/mark obsolete wrong records, update the correct record, and avoid creating a duplicate.
   - Related item: attach to existing plan as a milestone/task/update.
   - Truly new area: create a top-level plan.
   - Ambiguous: save a low-risk milestone/commitment or ask for confirmation instead of creating another top-level plan.

4. **Structure Hierarchically**
   - Top-level plans are durable and few.
   - Milestones carry sub-goals.
   - Commitments/tasks carry concrete next actions.
   - Entities are canonical and reused.

5. **Confirm and Clean**
   - Tell the user what changed:
     - archived
     - merged
     - updated
     - created
   - Keep memory/accountability output clean.

### Full Phase Map

1. **Phase 1 - Memory Discipline Foundation**
   - Add shared policy classes, decision types, and scoring rules.
   - Centralize the 5-step discipline process so all memory writes use the same behavior.

2. **Phase 2 - Entity Normalization Layer**
   - Add canonical entity name handling, aliases, stale-name correction, and pre-save normalization.
   - Make project/person/place names resistant to drift.

3. **Phase 3 - Plan Intelligence Layer**
   - Add routing logic that decides whether a candidate belongs to an existing plan, milestone, task, or new top-level plan.
   - Prevent flat duplicate plans.

4. **Phase 4 - Correction Execution and Cleanup**
   - Make corrections actionable: archive obsolete records, merge duplicates, update canonical records, and write audit metadata.
   - Provide repeatable cleanup scripts for existing data.

5. **Phase 5 - Chat and Prompt Integration**
   - Wire the discipline layer into chat/memory extraction.
   - Make Rex explain memory changes clearly after corrections or consolidations.

6. **Phase 6 - Accountability UI and Rollout Validation**
   - Ensure the frontend shows plans hierarchically and does not make the system look flat/noisy.
   - Add manual and automated regression cases before moving on.

### Files Expected Across All Phases

- `backend/supabase_schema.sql`
- `backend/app/services/memory_extraction_service.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/memory_service.py`
- `backend/app/services/entity_service.py`
- `backend/app/services/plan_service.py`
- `backend/app/services/rule_service.py`
- `backend/app/services/commitment_service.py`
- New backend services under `backend/app/services/`
- New backend models under `backend/app/models/`
- New scripts under `backend/scripts/`
- Tests under `tests/`
- Flutter accountability/memory pages under `lib/`

### Non-Goals

- Do not hard-code personal current-life logic as the general solution.
- Do not rely only on prompts when deterministic service-level checks can enforce behavior.
- Do not create another cleanup-only script without adding preventive logic.
- Do not make every chat turn ask for confirmation; confirmations are for ambiguous or high-impact merges only.

### Global Test Command

```bash
PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test
```

## Phase 1 - Memory Discipline Foundation

### Goal

Create the shared backend foundation for memory discipline decisions so every structured memory write can be routed through one consistent policy.

### Why This Matters

Right now, memory extraction can produce structured candidates, and individual services can deduplicate some records. The missing layer is a general decision point that says: create, update, merge, archive, attach as milestone, attach as task, or ask for confirmation.

### Checklist

1. [x] **Add discipline decision models**
   - Exact files to create or modify:
     - `backend/app/models/memory_discipline.py`
     - `tests/test_memory_discipline_service.py`
   - What must be implemented:
     - Models/enums for `MemoryCandidateKind`, `MemoryDisciplineAction`, `MemoryDisciplineDecision`, and `MemoryDisciplineContext`.
     - Action types:
       - `create_entity`
       - `update_entity`
       - `archive_entity`
       - `create_plan`
       - `update_plan`
       - `archive_plan`
       - `create_milestone`
       - `update_milestone`
       - `create_commitment`
       - `update_commitment`
       - `create_rule`
       - `update_rule`
       - `archive_rule`
       - `ask_confirmation`
       - `ignore_noisy_candidate`
   - Success criteria:
     - The rest of the backend can pass structured memory candidates through a typed decision API.
   - How to test:
     - Unit-test model validation and invalid action values.

2. [x] **Create MemoryDisciplineService**
   - Exact files to create or modify:
     - `backend/app/services/memory_discipline_service.py`
     - `tests/test_memory_discipline_service.py`
   - What must be implemented:
     - `class MemoryDisciplineService`
     - Method: `async decide(candidate, context) -> MemoryDisciplineDecision`
     - Method: `async gather_context(candidate) -> MemoryDisciplineContext`
     - Method: `async apply_decision(decision) -> dict`
   - Success criteria:
     - The service can retrieve active plans, milestones, commitments, rules, and entities before deciding what to do.
   - How to test:
     - Fake memory repository with existing records.
     - Verify related records are retrieved before decisions are made.

3. [x] **Implement deterministic matching helpers**
   - Exact files to create or modify:
     - `backend/app/services/memory_discipline_service.py`
     - `tests/test_memory_discipline_service.py`
   - What must be implemented:
     - Normalized text comparison.
     - Token overlap scoring.
     - Title similarity scoring.
     - Entity alias matching.
     - Source record matching.
     - Plan type matching.
   - Success criteria:
     - Similar items are detected without relying only on the LLM.
   - How to test:
     - `"$5k income"`, `"Reach 5k monthly income"`, and `"location independent income"` score as related.
     - `"Monday date with Melissa"` and `"Ask Melissa out for dinner"` score as related.
     - Unrelated topics do not cross-match.

4. [x] **Add discipline metadata standard**
   - Exact files to create or modify:
     - `backend/app/services/memory_discipline_service.py`
     - Existing service tests under `tests/`
   - What must be implemented:
     - Standard metadata keys:
       - `discipline_version`
       - `discipline_action`
       - `discipline_reason`
       - `merged_from_id`
       - `archived_by_correction_id`
       - `canonical_entity_id`
       - `source_candidate_kind`
       - `requires_confirmation`
   - Success criteria:
     - Every automatic merge/archive/update has traceable metadata.
   - How to test:
     - Apply a fake decision and assert metadata is written.

5. [x] **Wire service dependencies without changing behavior yet**
   - Exact files to create or modify:
     - `backend/app/dependencies.py` if present
     - `backend/app/services/chat_service.py`
     - `tests/test_chat_service.py`
   - What must be implemented:
     - Instantiate or inject `MemoryDisciplineService`.
     - Keep current behavior unchanged until later phases call it.
   - Success criteria:
     - No existing test behavior changes in this foundation phase.

### Exact Prompt / Rules To Add Later

Do not add the full prompt behavior in this phase. Add only this internal policy comment near the service:

```text
Memory discipline policy:
Before saving structured memory, Rex must check related active memory records and decide whether to update, merge, archive, create a milestone/task, create a new top-level plan, or ask for confirmation. Creating a new top-level plan is the last resort.
```

### How To Test

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_discipline_service.py
PYTHONPATH=backend python3 -m pytest -q tests
```

### Suggested Commit Message

`feat: add memory discipline foundation`

## Phase 2 - Entity Normalization Layer

### Goal

Prevent entity drift by normalizing names before save, preserving canonical entities, and treating user corrections as durable alias/correction rules.

### Why This Matters

If the user says a name was wrong, Rex must stop creating variants. This applies generally to people, projects, places, apps, organizations, jobs, and topics.

### Checklist

1. [x] **Design canonical entity schema support**
   - Exact files to create or modify:
     - `backend/supabase_schema.sql`
     - `backend/app/models/entity.py`
     - `tests/test_structured_memory_repository.py`
   - What must be implemented:
     - Add optional fields or metadata conventions for:
       - canonical entity ID
       - alias source
       - obsolete aliases
       - correction confidence
     - Prefer minimal schema if possible:
       - keep `entities.aliases`
       - store obsolete/correction metadata in `entities.metadata`
       - use `memory_corrections` for audit trail
   - Success criteria:
     - Canonical names and obsolete names can be represented without creating active duplicate entities.

2. [x] **Create EntityNormalizationService**
   - Exact files to create or modify:
     - `backend/app/services/entity_normalization_service.py`
     - `tests/test_entity_normalization_service.py`
   - What must be implemented:
     - `normalize_candidate_entity(candidate, known_entities)`
     - `resolve_canonical_name(raw_name, entity_type)`
     - `detect_obsolete_alias(raw_name, known_entities)`
     - `apply_user_correction(old_value, new_value, entity_type)`
   - Success criteria:
     - The service can rewrite stale names to canonical names before any entity/plan/rule/commitment is saved.
   - How to test:
     - Given known entity `EchoDesk` with obsolete alias `Echotask`, a candidate named `Echotask` resolves to `EchoDesk`.
     - Given known person correction `Al -> Melissa`, future `Al` references do not create active `Al`.

3. [x] **Generalize project/person/place correction handling**
   - Exact files to create or modify:
     - `backend/app/services/entity_service.py`
     - `backend/app/services/memory_discipline_service.py`
     - `tests/test_entity_service.py`
     - `tests/test_memory_discipline_service.py`
   - What must be implemented:
     - Detect correction language:
       - `not X, Y`
       - `X was wrong`
       - `delete mentions of X`
       - `real name is Y`
       - `I misspoke`
       - `merge X into Y`
     - Archive active wrong entity when it is truly obsolete.
     - Update canonical entity aliases only with acceptable aliases, not obsolete names the user wants removed.
   - Success criteria:
     - Wrong entities are archived or marked obsolete; canonical entity remains active.

4. [x] **Normalize entity references inside other structured records**
   - Exact files to create or modify:
     - `backend/app/services/memory_discipline_service.py`
     - `backend/app/services/plan_service.py`
     - `backend/app/services/rule_service.py`
     - `backend/app/services/commitment_service.py`
     - `tests/test_memory_discipline_service.py`
   - What must be implemented:
     - Before saving a plan, rule, milestone, or commitment, normalize text fields and entity references using canonical entities.
     - If a candidate says an obsolete project/person name, rewrite text to canonical name and link `primary_entity_id` / `entity_id` where possible.
   - Success criteria:
     - Wrong names cannot reappear in active plans or milestones through future extraction.

5. [x] **Add canonical correction prompt rules**
   - Exact files to create or modify:
     - `backend/app/services/memory_extraction_service.py`
     - `tests/test_memory_extraction.py`
   - Exact prompt/rules to add:
     ```text
     Entity normalization rules:
     - If the user corrects a name, spelling, identity, relationship, or label, treat the corrected value as canonical.
     - Do not save the wrong value as current truth or as an active alias when the user asked to remove it.
     - Before creating a new entity, check whether the name is an alias, obsolete name, spelling variant, or correction of an existing active entity.
     - If an obsolete name appears in a new candidate, rewrite it to the canonical entity name and link to the canonical entity.
     ```
   - Success criteria:
     - LLM output is less noisy, while deterministic service checks still enforce correctness.

### How To Test

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_entity_normalization_service.py tests/test_entity_service.py tests/test_memory_extraction.py
```

### Suggested Commit Message

`feat: add canonical entity normalization`

## Phase 3 - Plan Intelligence Layer

### Goal

Add the permanent plan-routing layer that prevents top-level plan spam and turns related goals into milestones or tasks under existing plans.

### Why This Matters

The system should not create a new plan every time the user mentions a goal. A plan is a durable container. Updates, sub-goals, deadlines, and concrete actions should become milestones or tasks/checklist items.

### Checklist

1. [x] **Define the plan hierarchy contract**
   - Exact files to create or modify:
     - `backend/app/models/plan.py`
     - `backend/app/models/commitment.py`
     - `backend/supabase_schema.sql`
     - `supabase/migrations/20260520165211_add_commitment_milestone_id.sql`
     - `docs/action_plans/rex_brain_system.md`
   - What must be implemented:
     - Decide whether checklist items should use existing `commitments` or a new `plan_tasks` table.
     - Recommended minimal schema:
       - Add nullable `milestone_id` to `commitments`.
       - Keep `commitments.plan_id`.
       - Use commitments as checklist/task items.
   - Success criteria:
     - Rex can represent `Plan -> Milestone -> Task/Commitment` without flat plan duplication.

2. [x] **Create PlanIntelligenceService**
   - Exact files to create or modify:
     - `backend/app/services/plan_intelligence_service.py`
     - `tests/test_plan_intelligence_service.py`
   - What must be implemented:
     - `class PlanIntelligenceService`
     - Methods:
       - `classify_plan_candidate(candidate, context)`
       - `find_best_parent_plan(candidate, active_plans)`
       - `find_related_milestone(candidate, active_milestones)`
       - `should_create_top_level_plan(candidate, context)`
       - `build_milestone_from_plan_candidate(candidate, parent_plan)`
       - `build_commitment_from_small_step(candidate, parent_plan, milestone=None)`
   - Success criteria:
     - A candidate can be routed to create/update plan, create/update milestone, create/update commitment, or ask confirmation.
   - How to test:
     - Income targets route under relocation/freedom plan.
     - App launch sub-goals route under app development plan.
     - Dating logistics route under one dating plan for the person.
     - Truly unrelated health goal creates a new health plan only if no parent exists.

3. [x] **Add strict top-level plan creation rules**
   - Exact files to create or modify:
     - `backend/app/services/plan_intelligence_service.py`
     - `backend/app/services/plan_service.py`
     - `tests/test_plan_intelligence_service.py`
     - `tests/test_plan_service.py`
   - What must be implemented:
     - A new top-level plan requires:
       - distinct life/work area OR distinct long-running project
       - no sufficiently similar active plan
       - durable time horizon
       - enough specificity to be useful
     - A new top-level plan is rejected or downgraded when:
       - same entity/person/project as existing plan
       - same outcome with different wording
       - only a deadline, next step, update, or reflection
       - can fit as milestone/commitment
   - Success criteria:
     - The default route for related updates is not `create_plan`.

4. [x] **Implement merge/update behavior**
   - Exact files to create or modify:
     - `backend/app/services/plan_service.py`
     - `backend/app/services/plan_intelligence_service.py`
     - `tests/test_plan_service.py`
     - `tests/test_plan_intelligence_service.py`
   - What must be implemented:
     - If a candidate overlaps an existing plan:
       - update plan summary if the new detail changes the big picture
       - create milestone if it is a sub-goal
       - create commitment if it is a concrete action
       - archive duplicate plan if one already exists
   - Success criteria:
     - Existing top-level plan stays clean and accumulates structured children.

5. [x] **Add plan intelligence prompt rules**
   - Exact files to create or modify:
     - `backend/app/services/memory_extraction_service.py`
     - `tests/test_memory_extraction.py`
   - Exact prompt/rules to add:
     ```text
     Plan intelligence rules:
     - A top-level plan is a durable container for a major area of life or work.
     - Do not create a new top-level plan for progress updates, repeated goals, deadlines, single next actions, or alternate wording.
     - If a candidate belongs under an active plan, output it as a plan_milestone or commitment instead.
     - Income, savings, client acquisition, and app revenue details should attach to the user's broader life/work plan when related.
     - Date logistics for the same person should attach to one dating plan for that person.
     - When unsure, prefer a milestone/commitment or ask for confirmation instead of creating a duplicate plan.
     ```
   - Success criteria:
     - LLM candidates are closer to the desired hierarchy before deterministic enforcement runs.

### How To Test

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_plan_intelligence_service.py tests/test_plan_service.py tests/test_plan_consolidation.py
```

### Suggested Commit Message

`feat: add plan intelligence routing`

## Phase 4 - Correction Workflows

### Goal

Make user corrections immediately actionable across memory: archive wrong records, update correct records, merge duplicates, and keep audit metadata.

### Why This Matters

When the user says "that is wrong", Rex must not merely agree in chat. It must apply the correction to memory and prevent the old version from continuing to appear.

### Checklist

1. [ ] **Create correction intent detector**
   - Exact files to create or modify:
     - `backend/app/services/memory_correction_service.py`
     - `tests/test_memory_correction_service.py`
   - What must be implemented:
     - Detect correction intents:
       - wrong name
       - wrong relationship
       - wrong plan structure
       - duplicate plan
       - remove obsolete memory
       - merge item into parent
       - replace old value with new value
   - Success criteria:
     - Corrections can be classified before structured extraction creates new records.
   - How to test:
     - Test phrases such as:
       - `not X, it is Y`
       - `delete any mention of X`
       - `merge these plans`
       - `that should be under the Europe plan`
       - `this is not a plan, it is just a task`

2. [ ] **Implement correction execution**
   - Exact files to create or modify:
     - `backend/app/services/memory_correction_service.py`
     - `backend/app/services/memory_service.py`
     - `tests/test_memory_correction_service.py`
   - What must be implemented:
     - Apply corrections to:
       - `long_term_memory`
       - `entities`
       - `entity_events`
       - `personal_rules`
       - `plans`
       - `plan_milestones`
       - `commitments`
     - Archive obsolete records instead of deleting them unless the user explicitly asks for hard deletion and the app supports it.
   - Success criteria:
     - Wrong active records stop appearing in normal active-memory views.

3. [ ] **Use memory_corrections as audit trail**
   - Exact files to create or modify:
     - `backend/app/services/memory_correction_service.py`
     - `backend/app/services/memory_service.py`
     - `tests/test_memory_correction_service.py`
   - What must be implemented:
     - Every correction writes a `memory_corrections` record with:
       - old value
       - new value
       - target table
       - target ID
       - applied status
       - confidence
       - metadata with affected records
   - Success criteria:
     - Corrections are traceable and debuggable.

4. [ ] **Add confirmation behavior for high-impact merges**
   - Exact files to create or modify:
     - `backend/app/services/memory_correction_service.py`
     - `backend/app/services/chat_service.py`
     - `backend/app/models/chat.py`
     - `tests/test_chat_service.py`
   - What must be implemented:
     - Immediate automatic correction when user is explicit.
     - Ask for confirmation when:
       - merge would archive several active records
       - correction is ambiguous
       - potential data loss is high
     - Keep confirmation payload machine-readable.
   - Success criteria:
     - Rex can say exactly what it plans to merge/archive and wait for approval when needed.

5. [ ] **Replace cleanup scripts with reusable correction workflows**
   - Exact files to create or modify:
     - `backend/scripts/consolidate_plans.py`
     - `backend/scripts/cleanup_project_names.py`
     - New optional `backend/scripts/apply_memory_discipline.py`
     - `tests/test_plan_consolidation.py`
     - `tests/test_project_name_cleanup.py`
   - What must be implemented:
     - Keep scripts, but make them call shared services.
     - Scripts become operational tools, not unique logic.
   - Success criteria:
     - One code path handles live chat corrections and batch cleanups.

### Exact Prompt / Rules To Add

Add to memory extraction and/or chat correction prompt:

```text
Correction execution rules:
- If the user explicitly corrects memory, do not just acknowledge it.
- Apply the correction to active structured memory.
- Archive or mark obsolete the wrong record when keeping it active would confuse future retrieval.
- Update the correct record with the new durable detail.
- Do not create a new duplicate record as the correction mechanism.
- After applying the change, summarize exactly what was archived, updated, merged, or created.
```

### How To Test

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_correction_service.py tests/test_chat_service.py tests/test_plan_consolidation.py tests/test_project_name_cleanup.py
```

### Suggested Commit Message

`feat: apply memory corrections across structured records`

## Phase 5 - Chat and Prompt Integration

### Goal

Wire the discipline system into the live Rex chat flow so it becomes the default behavior of the agent before memory is saved.

### Why This Matters

The backend can have good services, but if chat still saves raw extraction output directly, duplication and drift will return. The discipline layer must sit between extraction and persistence.

### Checklist

1. [ ] **Route extraction output through MemoryDisciplineService**
   - Exact files to create or modify:
     - `backend/app/services/memory_extraction_service.py`
     - `backend/app/services/chat_service.py`
     - `backend/app/services/memory_discipline_service.py`
     - `tests/test_memory_extraction.py`
     - `tests/test_chat_service.py`
   - What must be implemented:
     - Existing extracted candidates become inputs to the discipline service.
     - The discipline service decides what actually gets saved.
   - Success criteria:
     - The LLM can suggest candidates, but deterministic discipline controls final writes.
   - How to test:
     - Fake extraction returns duplicate plan; chat saves milestone instead.

2. [ ] **Add memory-change response summary**
   - Exact files to create or modify:
     - `backend/app/models/chat.py`
     - `backend/app/services/chat_service.py`
     - `lib/features/chat/domain/chat_message.dart`
     - `lib/features/chat/presentation/pages/chat_page.dart` if needed
     - `tests/test_chat_service.py`
   - What must be implemented:
     - Internal summary of memory writes:
       - created
       - updated
       - archived
       - merged
       - skipped
       - confirmation required
     - Decide whether to expose summary in assistant text or metadata only.
   - Success criteria:
     - User can understand what Rex actually changed after a correction.

3. [ ] **Add final discipline prompt block**
   - Exact files to create or modify:
     - `backend/app/services/memory_extraction_service.py`
     - `backend/app/services/prompt_service.py`
     - `tests/test_memory_extraction.py`
   - Exact prompt/rules to add:
     ```text
     Memory Discipline rules:
     - Prefer updating existing memory over creating new memory.
     - Before saving a plan, goal, rule, task, or entity, consider whether it belongs to an active existing record.
     - Corrections from the user override prior memory.
     - A duplicate active plan/rule/entity is a memory quality error.
     - Use top-level plans only for durable major areas.
     - Use milestones for sub-goals, deadlines, and progress details.
     - Use commitments for concrete actions, habits, or checklist items.
     - Use entity events for relationship changes, interactions, or historical notes.
     - Never preserve stale wrong names as current truth.
     ```
   - Success criteria:
     - Prompts guide extraction, while services enforce behavior.

4. [ ] **Add confirmation UX for ambiguous discipline decisions**
   - Exact files to create or modify:
     - `backend/app/models/chat.py`
     - `backend/app/services/chat_service.py`
     - `lib/features/chat/presentation/pages/chat_page.dart`
     - `lib/features/chat/presentation/widgets/chat_input_bar.dart` if needed
     - `tests/test_chat_service.py`
     - Flutter widget tests if UI changes are visible
   - What must be implemented:
     - Rex can ask:
       - `I found 4 overlapping goals under Relocate to Europe. Merge them into milestones?`
     - User approval applies the pending correction/merge.
   - Success criteria:
     - Ambiguous high-impact cleanup is safe but not blocked forever.

5. [ ] **Prevent save loops and double writes**
   - Exact files to create or modify:
     - `backend/app/services/chat_service.py`
     - `backend/app/services/memory_discipline_service.py`
     - `tests/test_chat_service.py`
   - What must be implemented:
     - Ensure one user turn cannot create both a duplicate plan and its milestone.
     - Ensure correction application does not trigger a second extraction save of the same content.
   - Success criteria:
     - Each candidate has one final action.

### How To Test

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_chat_service.py tests/test_memory_extraction.py tests/test_memory_discipline_service.py
```

### Suggested Commit Message

`feat: enforce memory discipline in chat flow`

## Phase 6 - Accountability UI and Rollout

### Goal

Make the cleaned memory structure visible and trustworthy in the app, then validate the full system with regression cases before moving to the next major action plan.

### Why This Matters

If the backend stores hierarchy but the UI still presents everything as flat noise, the user will still feel like memory is broken. The Accountability screen should show a small number of active plans with milestones and tasks underneath.

### Checklist

1. [ ] **Update accountability overview shape**
   - Exact files to create or modify:
     - `backend/app/routes/accountability.py`
     - `backend/app/services/accountability_service.py`
     - `backend/app/models/accountability.py`
     - `tests/test_accountability_service.py`
     - `tests/test_accountability_routes.py`
   - What must be implemented:
     - Group active milestones under their parent plans.
     - Group open commitments/checklist items under plan or milestone when linked.
     - Include counts:
       - active top-level plans
       - open milestones
       - open tasks/checklist items
       - duplicate-risk warnings
   - Success criteria:
     - API output reflects hierarchy instead of only flat lists.

2. [ ] **Update Flutter accountability display**
   - Exact files to create or modify:
     - `lib/features/memory/` or existing accountability page files
     - `lib/services/chat_api.dart` or API client files
     - Flutter tests under `test/`
   - What must be implemented:
     - Show top-level plans as primary sections.
     - Show milestones nested under plans.
     - Show commitments/tasks as checklist rows when available.
     - Keep rules and signals separate from plans.
   - Success criteria:
     - User sees 2-5 big plans, not a wall of duplicated mini-goals.
   - How to test:
     - Widget test renders nested active plan structure.
     - `flutter analyze && flutter test`

3. [ ] **Add memory discipline regression dataset**
   - Exact files to create or modify:
     - `tests/test_memory_discipline_regressions.py`
     - `docs/action_plans/rex_memory_regression_cases.md`
   - What must be implemented:
     - Regression cases for:
       - corrected entity names
       - duplicate dating plan
       - overlapping income plans
       - app/project name drift
       - duplicate rules
       - task misclassified as top-level plan
       - correction that should archive stale record
   - Success criteria:
     - The exact failure modes that caused plan spam and entity drift are covered.

4. [ ] **Create manual memory discipline test script**
   - Exact files to create or modify:
     - `docs/action_plans/rex_memory_manual_test.md`
   - What must be implemented:
     - Manual prompts to run through the mobile app:
       - new plan
       - related update
       - correction
       - duplicate goal
       - entity spelling fix
       - merge request
       - accountability review
   - Success criteria:
     - Founder can verify behavior without reading DB records.

5. [ ] **Add rollout/migration script**
   - Exact files to create or modify:
     - `backend/scripts/apply_memory_discipline.py`
     - `backend/scripts/consolidate_plans.py`
     - Existing cleanup scripts
     - `tests/test_memory_discipline_rollout.py`
   - What must be implemented:
     - Dry-run first.
     - Apply only when explicitly requested.
     - Report:
       - records scanned
       - duplicate clusters
       - updates
       - archives
       - milestones/tasks created
       - errors
   - Success criteria:
     - Existing production data can be cleaned using the same discipline rules as future data.

6. [ ] **Run full validation and deploy**
   - Exact files to create or modify:
     - No code changes expected unless validation exposes issues
   - What must be implemented:
     - Run full backend and Flutter checks.
     - Run discipline dry-run against production.
     - Apply only after reviewing report.
     - Restart backend.
     - Verify `/ready`, `/plans`, `/accountability/overview`.
   - Verification commands:
     ```bash
     PYTHONPATH=backend python3 -m pytest -q tests
     flutter analyze
     flutter test
     PYTHONPATH=backend python3 backend/scripts/apply_memory_discipline.py --limit 500
     ```

### Exact User-Facing Confirmation Language

Use concise summaries like:

```text
I cleaned that up:
- Archived: "Monday outing with Melissa" as a duplicate plan.
- Kept: "Ask Melissa out for dinner" as the active plan.
- Added milestone: "Monday outing with Melissa" under that plan.
- No new top-level plan was created.
```

For ambiguous merges:

```text
I found several overlapping goals that look like they belong under "Relocate to Europe next year":
- $5k monthly income
- $600 monthly savings
- one-year location-independent income

Do you want me to merge these into milestones under the Europe plan?
```

### How To Test

```bash
PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test
```

### Suggested Commit Message

`feat: show disciplined memory hierarchy in accountability`

## Revision History

- 2026-05-20 - Created as combined Rex Brain System implementation plan from the original Memory Discipline phase files.
