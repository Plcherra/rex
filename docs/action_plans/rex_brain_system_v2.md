# Rex Brain System v2 - Trustworthy Memory

## Overview

Rex Brain System v2 is the reliability rebuild for Rex memory.

The current system made progress by reducing top-level plan sprawl, but it still allows a dangerous pattern: chat turns can produce structured memory writes automatically, and Rex can say "fixed" before the database is actually clean. v2 changes the default from automatic memory creation to confirmed, verified memory updates.

The new standard is:

```text
User speaks
-> Rex extracts pending memory candidates
-> Rex proposes exact changes
-> User confirms naturally by button or chat
-> Backend applies and verifies writes
-> Rex reports exactly what changed
```

No durable structured memory is saved until the user confirms it.

Confirmation should feel natural, not bureaucratic. Rex should accept clear chat confirmations like `yes`, `confirm`, `do it`, `apply`, `ok`, `save that`, and `approve all`, while still requiring explicit confirmation for high-risk changes.

### Core Philosophy

- Trust over speed.
- Quality over quantity.
- Memory writes must be explicit, confirmed, and verifiable.
- Rex must never claim "saved", "fixed", "updated", "merged", or "archived" unless the backend confirms the operation succeeded.
- Plans are few and rich.
- Milestones are achievements, not a dumping ground.
- Tasks are concrete next actions.
- Entity events are historical facts.
- Corrections must remove stale truth, not add a new layer on top of it.

### Current Problem v2 Solves

The current system can:

- Save noisy plan/milestone fragments without confirmation.
- Extract durable memory from assistant responses.
- Move duplicate plans into duplicate milestones.
- Leave false facts active after a correction.
- Report zero duplicates while the UI shows duplicate milestones.
- Show internal memory fragments as if they are user-facing goals.

v2 fixes the source of the mess before another cleanup run.

## Target Memory Model

### 1. Conversation Log

Purpose:

- Store raw chat and voice turns.
- Preserve continuity.
- Never act as durable truth by itself.

Save behavior:

- Automatic.

Examples:

- User transcript.
- Assistant response.
- Voice metadata.

### 2. Pending Memory Candidates

Purpose:

- Hold proposed memory changes before they become durable.
- Let the user approve, edit, or reject.

Save behavior:

- Automatic as pending only.
- No durable memory write happens yet.
- Each candidate has a risk level: `low`, `medium`, or `high`.
- Optional auto-apply is allowed only for low-risk candidates and only if the user has enabled that behavior. Default behavior is no auto-apply.

Examples:

- "Candidate: update Stephanie summary."
- "Candidate: create task to verify Italian citizenship eligibility."
- "Candidate: archive duplicate Melissa milestones."

Risk examples:

- Low risk: small task/checklist item, harmless entity event, spelling cleanup.
- Medium risk: new commitment, plan description update, non-destructive entity update.
- High risk: new top-level plan, archive/merge, correction that touches multiple records, person relationship correction, anything that could remove or overwrite durable memory.

### 3. Top-Level Plans

Definition:

- Durable life/work areas that last weeks or months.
- Rare: normally 2-5 active plans.
- Always user-confirmed.
- Always require a clear description.

Required fields:

- `title`
- `plan_type`
- `description`
- `desired_outcome`
- `priority`
- `status`

Description must include:

- Overall goal.
- Success criteria.
- Main routes or strategy.
- Income/timeline targets when relevant.
- Current known constraints.

Creation/update rule:

- Rex must propose a rich description before creating or materially updating a top-level plan.
- The user must confirm or edit that description before the plan becomes durable memory.

Examples:

- `Move out of the country next year`
- `Launch and monetize Clarity, EchoDesk, and FlowForce`
- `Melissa follow-up`

Not allowed:

- Creating a top-level plan for every update.
- Creating a top-level plan from exploratory questions.
- Creating a top-level plan from assistant advice.
- Creating a plan without a description.

### 4. Milestones

Definition:

- Achievement checkpoints or trophies.
- They should feel like something the user can earn or complete.
- They should not be a list of every plan-related thought.

Examples:

- `Clarity launched`
- `EchoDesk launched`
- `FlowForce launched`
- `$3k/month revenue reached`
- `$5k/month profit reached`
- `Italian citizenship eligibility confirmed`
- `Italian citizenship application submitted`

Not allowed:

- `Europe Move`
- `Project Sequence`
- `Three-month app development plan`
- `Next week date with Melissa`
- `One-year location-independent income`
- `Reach first million` when the user only asked how long it might take.

### 5. Tasks / Commitments

Definition:

- Concrete next actions, habits, or checklist items.
- User can mark them done.

Examples:

- `Verify Italian citizenship eligibility under current law`
- `Gather great-grandmother citizenship documents`
- `Prepare Clarity release build`
- `Define EchoDesk MVP scope`
- `Research Portugal D7 income requirements`

Not allowed:

- Vague goals.
- Assistant-generated strategy paragraphs.
- Duplicate phrasings of the same action.

### 6. Entity Events

Definition:

- Historical facts, relationship updates, interactions, corrections, and notable events.
- These should not become plans or milestones unless the user explicitly wants to track action.

Examples:

- `Stephanie quit about a month ago`
- `Lara got fired at the beginning of the year`
- `Melissa said she would tell the user her response`
- `Greece is a place the user likes and may visit`

### 7. People / Entities

Definition:

- Canonical summaries for people, projects, places, organizations, and topics.
- Must preserve corrected names and avoid stale aliases.

Examples:

- `Clarity`
- `EchoDesk`
- `FlowForce`
- `Melissa`
- `Stephanie`
- `Lara`
- `Portugal`

Rules:

- Corrected names become canonical.
- Stale names must be archived or marked obsolete.
- Wrong facts must not remain active.

## Target Examples

### Relocation / Move-Out Plan

Top-level plan:

- Title: `Move out of the country next year`
- Type: `immigration`
- Description:
  - The user wants to leave the current country next year.
  - Primary route is Italian citizenship by descent through great-grandmother.
  - If eligibility is blocked by law changes, fallback is Portugal D7 or digital nomad visa.
  - Portugal is the primary relocation target because it can lead to residency/citizenship over time.
  - Greece is a place to visit, not the current primary relocation target.
  - Income target is around `$3k/month` by end of year and around `$5k/month` or `$5k profit/month` before moving.
  - Revenue can come from Clarity, EchoDesk, FlowForce, subscriptions, Upwork, or custom projects.
- Desired outcome:
  - User has legal route, income runway, and practical readiness to move.

Tasks:

- Verify Italian citizenship eligibility under current law.
- Gather ancestry/citizenship documents.
- Research Portugal D7/digital nomad visa requirements.
- Track monthly revenue toward `$3k/month`.
- Track profit/runway toward `$5k/month`.

Milestones:

- `Italian citizenship eligibility confirmed`
- `Italian citizenship application submitted`
- `$3k/month revenue reached`
- `$5k/month profit reached`
- `Portugal fallback route ready`
- `Move date selected`

Entity events:

- `Greece is a place the user likes and may visit`
- `Portugal is the current fallback/primary visa route if Italian citizenship is blocked`

### App Launch Plan

Top-level plan:

- Title: `Launch and monetize Clarity, EchoDesk, and FlowForce`
- Type: `career`
- Description:
  - Launch Clarity first in about 2-3 weeks.
  - Clarity is the app name replacing Rex for the user-facing app.
  - Clarity includes the Rex personal advisor and the financial/transactions functionality.
  - Launch EchoDesk around mid/end of next month.
  - Launch FlowForce by the end of the following month.
  - Use the shipped apps for subscriptions, portfolio proof, Upwork credibility, and custom project opportunities.
- Desired outcome:
  - Three usable apps are live and help generate subscription revenue, Upwork work, or custom project income.

Tasks:

- Prepare Clarity release build.
- Finish Clarity financial/transaction features.
- Prepare Clarity account/subscription/testing flow.
- Define EchoDesk MVP scope.
- Define FlowForce MVP scope.
- Add portfolio/demo material for Upwork.

Milestones:

- `Clarity launched`
- `EchoDesk launched`
- `FlowForce launched`
- `First subscription user`
- `First paid custom/client project from portfolio`

Entity normalization:

- `Rex` as user-facing app name should be replaced by `Clarity` where appropriate.
- `EchoDesk` is canonical.
- `FlowForce` is canonical.
- Do not save `Flowfirst`, `Flowforte`, `Echotask`, `Flow`, or `Flow Force` as active canonical app names.

### Melissa Follow-Up

Top-level plan:

- Title: `Melissa follow-up`
- Type: `dating`
- Description:
  - User already asked Melissa out.
  - Melissa said she would tell him her response.
  - User thinks she is likely not interested.
  - Continue only if Melissa responds or there is a meaningful new interaction.
- Desired outcome:
  - Clear answer from Melissa, with no duplicate open date plans.

Tasks:

- None by default.

Milestones:

- None by default.

Entity events:

- `User asked Melissa out`
- `Melissa said she would tell him her response`
- `User thinks Melissa is likely not interested`

### Income Target

This should not be a separate duplicate plan unless the user explicitly asks for a standalone finance plan.

It belongs under the move-out plan as prerequisite progress.

Canonical target:

- `$3k/month revenue by end of year`
- then roughly `$5k/month` or `$5k profit/month` before moving

Revenue sources:

- app subscriptions
- Upwork
- custom projects
- Clarity
- EchoDesk
- FlowForce

Milestones:

- `$3k/month revenue reached`
- `$5k/month profit reached`

Tasks:

- Track monthly revenue.
- Track subscription revenue separately from client/custom income.
- Keep weekly small releases.

## Global v2 Rules

### Memory Write Rules

Add this rule to the extraction and chat prompts:

```text
Structured memory must not be written directly from chat extraction.
Create pending memory candidates first.
Only apply durable writes after explicit user confirmation.
Never say "saved", "fixed", "updated", "merged", or "archived" unless the backend reports the write succeeded and verification passed.
```

### Extraction Rules

Add this rule to `MEMORY_EXTRACTION_PROMPT`:

```text
Extract durable memory only from user-stated facts, explicit user corrections, or confirmed backend operation results.
Do not extract durable memory from assistant advice, assistant summaries, assistant guesses, or assistant claims that something was fixed.
When in doubt, create a pending candidate with low confidence instead of writing durable memory.
```

### Plan Rules

Add this rule:

```text
Top-level plans are rare, durable, user-confirmed containers.
Every top-level plan must have a clear description with overall goal, success criteria, main strategy, and timeline/income targets when relevant.
If description is missing or vague, ask/propose one before saving.
```

### Milestone Rules

Add this rule:

```text
Milestones are achievement checkpoints, like medals or trophies.
Do not create milestones from alternate plan wording, broad strategy, assistant advice, exploratory questions, or repeated logistics.
If the item is an action, make it a task/commitment.
If the item is historical context, make it an entity event.
If the item duplicates an existing milestone, update or ignore it.
```

### Correction Rules

Add this rule:

```text
Corrections must update the canonical record, archive stale records, and verify no active memory still contains the wrong fact.
If verification fails, report the remaining stale records instead of claiming the correction is fixed.
```

### Confirmation Rules

Add this rule:

```text
Treat short confirmations like "yes", "ok", "do it", "confirm", "apply", "save that", "looks good", and "approve all" as approval only when there are pending memory candidates in the current conversation.
If there are multiple pending candidates and the user says "yes" ambiguously, ask whether they mean the latest candidate or all candidates.
If the user says "approve all", apply every pending candidate in the current conversation that does not require separate high-risk confirmation.
High-risk candidates always require explicit candidate-specific confirmation.
```

### Risk-Level Rules

Add this rule:

```text
Every pending memory candidate must have a risk level.
Low-risk candidates are small reversible additions like simple tasks or harmless entity events.
Medium-risk candidates update existing durable memory without archiving or broad rewrites.
High-risk candidates create top-level plans, archive/merge records, correct person facts, or affect multiple records.
Auto-apply is disabled by default and can only be enabled for low-risk candidates after the user opts in.
```

## Phase 1a - Memory Candidate Foundation

### Goal

Add the `memory_candidates` table, backend model, service, and API routes. This phase creates the foundation only; it does not yet reroute chat extraction.

### Files To Create / Modify

- `backend/supabase_schema.sql`
- `supabase/migrations/<timestamp>_add_memory_candidates.sql`
- `backend/app/models/memory_candidate.py`
- `backend/app/services/memory_candidate_service.py`
- `backend/app/dependencies.py`
- `backend/app/routes/memory_candidates.py`
- `backend/app/main.py`
- `tests/test_memory_candidate_service.py`
- `tests/test_memory_candidate_routes.py`

### Data Model

Create table `memory_candidates`.

Required columns:

- `id uuid primary key`
- `candidate_type text not null`
- `payload jsonb not null`
- `status text not null default 'pending'`
- `risk_level text not null default 'medium'`
- `decision jsonb`
- `reason text`
- `source_conversation_id uuid`
- `source_message_id uuid`
- `approved_by text`
- `approved_at timestamptz`
- `applied_at timestamptz`
- `rejected_at timestamptz`
- `applied_record_table text`
- `applied_record_id uuid`
- `verification jsonb`
- `created_at timestamptz default now()`
- `updated_at timestamptz default now()`

Allowed statuses:

- `pending`
- `approved`
- `rejected`
- `applied`
- `failed`

Allowed candidate types:

- `long_term_memory`
- `entity`
- `entity_event`
- `personal_rule`
- `plan`
- `plan_milestone`
- `commitment`
- `correction`
- `archive`
- `merge`

Risk levels:

- `low`
- `medium`
- `high`

Optional indexes:

- `(status, created_at)`
- `(source_conversation_id, status, created_at)`
- `(candidate_type, status)`
- `(risk_level, status)`

### Checklist

1. [x] Add Supabase migration for `memory_candidates`.
2. [x] Add model request/response types.
3. [x] Add repository methods to create/list/update candidates.
4. [x] Add risk-level field and validator.
5. [x] Add `approve_candidate()` service method placeholder, but keep durable apply behind a feature flag until Phase 1b.
6. [x] Add `reject_candidate()` service method.
7. [x] Add `bulk_approve_candidates()` and `bulk_reject_candidates()` service methods.
8. [x] Add API routes:
   - `GET /memory-candidates`
   - `POST /memory-candidates/{id}/approve`
   - `POST /memory-candidates/{id}/reject`
   - `PATCH /memory-candidates/{id}`
   - `POST /memory-candidates/approve-all`
   - `POST /memory-candidates/reject-all`
9. [x] Add route filters for conversation, status, type, and risk level.
10. [x] Add candidate response shape that includes human-readable preview text.
11. [x] Add tests for create/list/edit/reject/bulk operations.
12. [x] Add tests proving candidate records do not create durable memory by themselves.

### Prompt Rules To Add

```text
Pending memory candidates are proposals, not durable memory.
Creating a candidate is not the same as saving memory.
Use candidate previews to show exactly what would change before approval.
```

### Test Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_candidate_service.py
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_candidate_routes.py
```

### Success Criteria

- `memory_candidates` exists locally and in Supabase migration.
- API can create, list, edit, reject, and bulk reject candidates.
- Candidate records include status, risk level, payload, source IDs, and preview.
- No durable structured memory is written by candidate creation.
- This phase can deploy without changing chat behavior.

## Phase 1b - Chat Extraction to Pending Candidates Only

### Goal

Stop direct structured memory writes from chat extraction. Chat extraction should create pending candidates only, and durable writes happen only after approval plus verification.

### Files To Create / Modify

- `backend/app/services/memory_extraction_service.py`
- `backend/app/services/memory_candidate_service.py`
- `backend/app/services/memory_discipline_service.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/prompt_service.py`
- `backend/app/routes/chat.py`
- `backend/app/routes/memory_candidates.py`
- `tests/test_memory_extraction.py`
- `tests/test_memory_candidate_service.py`
- `tests/test_chat_service.py`
- `tests/test_chat_routes.py`

### Checklist

1. [ ] Change `MemoryExtractionService` so structured sections create `memory_candidates` instead of durable records.
2. [ ] Keep long-term memory extraction conservative; convert durable long-term memory writes to candidates unless explicitly confirmed by the user.
3. [ ] Stop using assistant response text as authoritative extraction source.
4. [ ] Keep assistant response only as non-authoritative context when needed.
5. [ ] Attach `source_conversation_id` and `source_message_id` to every candidate.
6. [ ] Add candidate risk-level classifier.
7. [ ] Make top-level plan candidates require rich descriptions before approval.
8. [ ] On approval, apply through `MemoryDisciplineService`.
9. [ ] Run verification after every approved candidate.
10. [ ] Store verification result on the candidate.
11. [ ] Support approval phrases in chat:
    - `yes`
    - `ok`
    - `confirm`
    - `do it`
    - `apply`
    - `save that`
    - `looks good`
    - `approve all`
12. [ ] If the confirmation is ambiguous and multiple candidates exist, ask a short clarification.
13. [ ] Make `approve all` skip high-risk candidates unless the user explicitly confirms them.
14. [ ] Ensure `stream_message()` does not silently apply structured writes in the background.
15. [ ] Return pending/applied candidate status in chat responses.

### Natural Confirmation Behavior

Confirmation should work like this:

- If one pending candidate exists and the user says `yes`, approve it.
- If multiple low/medium-risk candidates exist and the user says `approve all`, bulk approve them.
- If high-risk candidates exist, Rex must name them and ask for explicit confirmation.
- If the user says `no`, `reject`, `don't save`, or `discard`, reject the latest pending candidate.
- If the user edits the proposed wording, update the candidate payload before approval.

### Prompt Rules To Add

```text
When you detect a possible durable memory update, propose it as a pending memory candidate.
Ask the user to confirm, edit, or reject it.
Accept natural confirmations only when they clearly refer to pending candidates.
Do not claim it is saved until approval and verification both succeed.
```

### Test Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_extraction.py
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_candidate_service.py
PYTHONPATH=backend python3 -m pytest -q tests/test_chat_service.py
PYTHONPATH=backend python3 -m pytest -q tests/test_chat_routes.py
```

### Success Criteria

- A chat turn can create pending candidates.
- No plan/milestone/entity/commitment/rule is created until approval.
- Approval writes the durable record through the discipline layer.
- Verification runs after every approved candidate.
- Rejection leaves durable memory unchanged.
- Rex cannot say "saved" unless the backend returns an applied and verified candidate.
- `approve all` works for eligible candidates.
- High-risk candidates cannot be bulk-applied without explicit confirmation.

## Phase 2 - Verified Corrections and Truth Cleanup

### Goal

Make corrections reliable and make verification a standard post-write step. A correction is complete only when stale facts are removed or archived and verification proves the wrong fact is no longer active.

### Files To Create / Modify

- `backend/app/services/memory_correction_service.py`
- `backend/app/services/memory_candidate_service.py`
- `backend/app/services/memory_verification_service.py`
- `backend/app/services/memory_service.py`
- `backend/app/routes/memory_candidates.py`
- `tests/test_memory_correction_service.py`
- `tests/test_memory_candidate_service.py`
- `tests/test_memory_verification_service.py`
- `tests/test_memory_discipline_regressions.py`

### Checklist

1. [ ] Create `MemoryVerificationService`.
2. [ ] Add cross-table search for stale terms across:
   - long-term memory
   - entities
   - entity events
   - plans
   - milestones
   - commitments
   - rules
3. [ ] Add correction candidate type.
4. [ ] Make correction apply path update canonical records and archive stale records.
5. [ ] Run verification after correction.
6. [ ] Store verification result on the candidate.
7. [ ] If verification fails, return remaining stale records to the chat/UI.
8. [ ] Add multi-entity correction tests:
   - Lara got fired.
   - Stephanie did not get fired.
   - Stephanie quit about a month ago.
9. [ ] Add tests that Rex cannot report full success when stale records remain.
10. [ ] Reuse verification service for every approved candidate, not only corrections.
11. [ ] Add standard verification payload:
    - `passed`
    - `checked_tables`
    - `remaining_conflicts`
    - `applied_record`
    - `message`

### Prompt Rules To Add

```text
For corrections, report only what the backend verified.
If stale active records remain, say exactly what still needs cleanup.
Do not summarize a correction as complete unless verification passed.
```

### Test Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_correction_service.py
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_verification_service.py
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_discipline_regressions.py
```

### Success Criteria

- Stephanie/Lara style corrections update all affected records.
- False facts do not remain active after a verified correction.
- Failed verification blocks "fixed" wording.
- Correction reports show updated, archived, and remaining stale records.
- Every approved candidate receives a verification result.
- Chat and UI can display verification status.

## Phase 3 - Stricter Plan Intelligence and Milestone Semantics

### Goal

Stop using milestones as a dumping ground. Plans become rich containers, tasks become actions, milestones become achievements.

### Files To Create / Modify

- `backend/app/services/plan_intelligence_service.py`
- `backend/app/services/memory_discipline_service.py`
- `backend/app/services/memory_extraction_service.py`
- `backend/scripts/consolidate_plans.py`
- `backend/scripts/apply_memory_discipline.py`
- `backend/app/models/plan.py`
- `tests/test_plan_intelligence_service.py`
- `tests/test_plan_consolidation.py`
- `tests/test_memory_discipline_regressions.py`

### Checklist

1. [ ] Require top-level plan descriptions.
2. [ ] Add plan description quality validator.
3. [ ] Add milestone classifier:
   - achievement
   - task
   - entity_event
   - duplicate
   - noisy_ignore
4. [ ] Prevent recursive milestones where title matches parent plan.
5. [ ] Prevent duplicate milestones under the same plan.
6. [ ] Stop consolidation script from creating milestone for every archived plan.
7. [ ] Merge useful duplicate plan details into parent plan description instead.
8. [ ] Route concrete actions into commitments/tasks.
9. [ ] Route historical context into entity events.
10. [ ] Add regression cases for relocation, app launch, Melissa, and income targets.

### Milestone Acceptance Rules

A candidate can become a milestone only if at least one is true:

- It represents a measurable completed or completable achievement.
- It has a concrete threshold.
- It is a launch/submission/approval/completion checkpoint.
- It can be shown as a progress badge without confusing the user.

Reject milestone if:

- It is just another title for the parent plan.
- It is a broad strategy.
- It is an exploratory question.
- It came from assistant advice.
- It duplicates another open milestone.
- It is a dating/logistics duplicate better represented as one entity event or task.

### Prompt Rules To Add

```text
Before creating a milestone, ask: would this look like a meaningful badge/trophy if completed?
If no, do not create a milestone.
Use a task for actions, an entity event for historical facts, and a plan description update for strategy.
```

### Test Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_plan_intelligence_service.py
PYTHONPATH=backend python3 -m pytest -q tests/test_plan_consolidation.py
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_discipline_regressions.py
```

### Success Criteria

- Duplicate Melissa date entries do not become five milestones.
- Relocation strategy variants do not become many open milestones.
- `Reach first million` is ignored or saved as low-priority context, not a plan/milestone.
- `Clarity launched`, `EchoDesk launched`, and `FlowForce launched` are valid milestones.
- App launch next actions become tasks.

## Phase 4 - Chat Confirmation UX and Memory Reporting

### Goal

Make chat memory behavior truthful. Rex should propose memory changes, ask for confirmation, apply them only after confirmation, then report exact verified results.

### Files To Create / Modify

- `backend/app/services/chat_service.py`
- `backend/app/services/prompt_service.py`
- `backend/app/routes/chat.py`
- `lib/features/chat/data/chat_models.dart`
- `lib/features/chat/data/chat_api.dart`
- `lib/features/chat/application/chat_controller.dart`
- `lib/features/chat/presentation/pages/chat_page.dart`
- `lib/features/chat/presentation/widgets/chat_message_bubble.dart`
- `tests/test_chat_service.py`
- `tests/test_chat_routes.py`
- `test/chat_controller_test.dart`
- `test/chat_page_widget_test.dart`

### Checklist

1. [ ] Add pending candidate cards/chips in chat.
2. [ ] Cards should show candidate type, risk level, preview, and expected write action.
3. [ ] Add Approve/Edit/Reject buttons.
4. [ ] Add Approve All / Reject All controls when multiple candidates are pending.
5. [ ] Support "yes", "ok", "confirm", "do it", "apply", "save that", "looks good", "approve all", and "reject" as chat confirmation.
6. [ ] Keep candidate IDs linked to the conversation.
7. [ ] After approval, show exact applied changes:
   - updated
   - created
   - archived
   - merged
   - verification status
8. [ ] If verification fails, show what remains wrong.
9. [ ] Prevent assistant from inventing memory write results.
10. [ ] Make streaming and non-streaming chat return consistent memory status.
11. [ ] Add UX guardrail: high-risk candidates show a stronger confirmation state and cannot be approved accidentally by vague `ok`.
12. [ ] Add optional low-risk auto-apply setting, disabled by default.

### Prompt Rules To Add

```text
If memory candidates are pending, ask the user to approve, edit, or reject them.
If the user confirms, call the backend approval flow.
If the user says "approve all", bulk approve only eligible low/medium-risk candidates and list any high-risk candidates that still need explicit confirmation.
After approval, report only the backend result.
Never claim memory changed based only on your own text.
```

### Test Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_chat_service.py
PYTHONPATH=backend python3 -m pytest -q tests/test_chat_routes.py
flutter test test/chat_controller_test.dart
flutter test test/chat_page_widget_test.dart
```

### Success Criteria

- User sees proposed memory changes before durable save.
- "Yes" applies the latest pending candidate safely.
- "Approve all" applies eligible pending candidates and skips high-risk ones unless explicitly confirmed.
- Chat reports the applied database changes.
- Chat does not say "fixed" if writes fail.

## Phase 5 - Accountability and Memory UI Redesign

### Goal

Make the UI reflect the real memory model. Accountability should guide the user, not expose every internal memory fragment.

### Files To Create / Modify

- `backend/app/routes/accountability.py`
- `backend/app/models/accountability.py`
- `backend/app/services/accountability_service.py`
- `lib/features/accountability/data/accountability_models.dart`
- `lib/features/accountability/data/accountability_api.dart`
- `lib/features/accountability/presentation/pages/accountability_page.dart`
- `lib/features/memory/presentation/pages/memory_page.dart`
- `tests/test_accountability_routes.py`
- `tests/test_accountability_service.py`
- `test/accountability_page_test.dart`
- `test/memory_controller_test.dart`

### Checklist

1. [ ] Add duplicate warnings for milestones.
2. [ ] Add duplicate warnings for commitments.
3. [ ] Add conflicting-fact warnings for entities.
4. [ ] Change Accountability plan cards to show:
   - title
   - rich description
   - current task checklist
   - completed milestone badges
   - optional upcoming achievement targets
5. [ ] Hide raw open milestones by default.
6. [ ] Add "Internal memory" expansion section for raw milestones/candidates.
7. [ ] Add pending candidate review section.
8. [ ] Add cleanup warning if a plan has too many open milestones or duplicate clusters.
9. [ ] Add edit/delete/archive controls where appropriate.

### UI Display Rules

Accountability should prioritize:

1. Current risks/signals.
2. Active rules.
3. Open tasks/commitments.
4. Clean plan descriptions.
5. Completed or high-signal milestone badges.
6. Memory cleanup warnings.

It should not default to showing every raw open milestone.

### Test Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_accountability_routes.py
PYTHONPATH=backend python3 -m pytest -q tests/test_accountability_service.py
flutter test test/accountability_page_test.dart
flutter analyze
```

### Success Criteria

- Duplicate Melissa milestones trigger duplicate warnings.
- 40+ open milestones is surfaced as a cleanup risk.
- Plan descriptions are visible.
- Tasks are easier to see than raw milestone fragments.
- Completed milestones display like achievements.

## Phase 6 - Current Data Cleanup and Rollout

### Goal

After preventive v2 changes are active, clean the current production data once.

Do not run this before Phases 1-5, or the system can recreate the same mess.

### Files To Create / Modify

- `backend/scripts/cleanup_rex_brain_v2_current_data.py`
- `backend/scripts/apply_memory_discipline.py`
- `backend/scripts/consolidate_plans.py`
- `docs/action_plans/rex_memory_manual_test.md`
- `tests/test_memory_discipline_rollout.py`
- `tests/test_plan_consolidation.py`

### Cleanup Targets

Relocation:

- Rename/replace `Relocate to Greece` with `Move out of the country next year`.
- Move Greece to entity event/preference as visit-only.
- Keep Italy citizenship route as primary.
- Keep Portugal D7/digital nomad as fallback.
- Collapse income targets into one prerequisite milestone/target.
- Archive duplicated relocation milestones.
- Archive `Reach first million` as non-plan unless explicitly confirmed.

Apps:

- Rename plan to `Launch and monetize Clarity, EchoDesk, and FlowForce`.
- Replace user-facing `Rex` app wording with `Clarity` where appropriate.
- Archive `Launch Rex Melissa`.
- Archive recursive/noisy app milestones.
- Keep clean launch milestones and concrete tasks.

Melissa:

- Rename plan to `Melissa follow-up`.
- Update description with "asked already, she said she would respond, likely not interested."
- Archive duplicate date milestones.
- Keep entity events for historical interaction.

People:

- Update Lara/Laura as kitchen supervisor who got fired at beginning of the year.
- Update Stephanie as Lara/Laura's friend who lives with her and quit about a month ago.
- Verify no active Stephanie record says she got fired at beginning of the year.

### Checklist

1. [ ] Build dry-run cleanup script.
2. [ ] Output exact affected records before applying.
3. [ ] Require explicit `--apply`.
4. [ ] Run verification after cleanup.
5. [ ] Confirm production overview has acceptable counts.
6. [ ] Confirm duplicate warnings are zero for real reasons.
7. [ ] Confirm UI shows clean plan descriptions and tasks.

### Test Commands

```bash
PYTHONPATH=backend python3 backend/scripts/cleanup_rex_brain_v2_current_data.py --dry-run --limit 500
PYTHONPATH=backend python3 -m pytest -q tests/test_memory_discipline_rollout.py
PYTHONPATH=backend python3 -m pytest -q tests/test_plan_consolidation.py
```

### Production Commands

Only after dry-run review:

```bash
PYTHONPATH=backend python3 backend/scripts/cleanup_rex_brain_v2_current_data.py --apply --limit 500
curl -sS 'https://api.rexpilot.com/accountability/overview?limit=100' | python3 -m json.tool
```

### Success Criteria

- Active plans are clean and accurately named.
- Open milestones are dramatically reduced.
- Melissa has one clean plan or event, not five duplicate milestones.
- Stephanie correction is verified.
- No wrong app names are active.
- Accountability UI is readable.

## Global Regression Cases

Add these test scenarios before rollout is considered complete.

### Confirmation Required

Input:

```text
I plan to move to Portugal next year.
```

Expected:

- Creates pending candidate.
- Does not directly create/update plan.
- User must confirm.

### Assistant Response Not Durable Truth

Input:

```text
Clean up all duplicates.
```

Assistant says:

```text
Done.
```

Expected:

- The word `Done` is not saved as memory truth.
- No durable cleanup is claimed without backend operation result.

### Milestone Gate

Input:

```text
I asked how long it would take to make my first million.
```

Expected:

- Does not create `Reach first million` milestone.
- May create no memory, or a low-priority pending entity event only if useful.

### Stephanie Correction

Input:

```text
Lara got fired at the beginning of this year. Stephanie was not fired; she quit about a month ago.
```

Expected:

- Pending correction candidate.
- On approval:
  - Lara updated.
  - Stephanie updated.
  - no active Stephanie fired fact remains.
  - verification passes.

### Melissa Duplicate

Existing:

- `Monday outing with Melissa`
- `Date with Melissa next week`
- `Next week date with Melissa`
- `Monday date with Melissa`
- `Next-week dinner with Melissa`

Expected:

- Duplicate warning fires.
- Cleanup proposes archiving duplicates.
- One `Melissa follow-up` plan or entity event remains.

### App Naming

Input:

```text
Rex will become Clarity as the app name.
```

Expected:

- Pending candidate to update app entity/plan wording.
- Does not create `Rex Melissa`.
- Does not create a new duplicate plan.

## Global Test Command

Run before deployment:

```bash
PYTHONPATH=backend python3 -m pytest -q tests
flutter analyze
flutter test
```

## Deployment Checklist

1. [ ] Run backend tests.
2. [ ] Run Flutter tests.
3. [ ] Apply Supabase migration.
4. [ ] Deploy backend.
5. [ ] Restart backend service.
6. [ ] Verify `/health`.
7. [ ] Verify pending candidates endpoint.
8. [ ] Verify chat creates candidates, not durable writes.
9. [ ] Verify candidate approval applies writes.
10. [ ] Verify Accountability UI is clean.
11. [ ] Run v2 cleanup dry-run.
12. [ ] Review dry-run output.
13. [ ] Run v2 cleanup apply.
14. [ ] Verify production memory state.

## Final Target

Rex memory should become boringly reliable:

- It proposes what it wants to remember.
- The user confirms.
- The backend applies.
- Verification proves it.
- The UI shows clean plans, real tasks, and meaningful achievements.

That is the line between a memory demo and a trustworthy daily system.
