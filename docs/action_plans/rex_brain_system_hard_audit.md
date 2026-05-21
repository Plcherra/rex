# Rex Brain System - Hard Audit

## Audit Date

2026-05-20

## Verdict

The system is not clear enough yet.

The first Rex Brain phases reduced top-level plan sprawl, but they moved too much noise into milestones. That made the Accountability screen look cleaner at the plan count level while still keeping the same duplication problem underneath.

The core failure is this:

> Rex still treats conversation fragments, assistant summaries, advice, guesses, and duplicate phrasings as durable structured memory.

That means the system can say "fixed" in chat while the saved memory remains wrong or becomes more bloated.

## Current Production Snapshot

Observed from `https://api.rexpilot.com/accountability/overview?limit=100`.

- Active plans: 3
- Open milestones: 42
- Open commitments: 4
- Active rules: 3
- Duplicate warnings: 0

The duplicate warning count is misleading because duplicate detection currently checks only active plans and rules. It does not check milestones, commitments, or entity facts.

## Current Misalignment

### 1. Relocation Plan

Current top-level plan:

- `Relocate to Greece`
- Description says the user will live in Greece.

This is wrong. The user's current clarified plan is:

- Move out of the country next year.
- Primary route: Italian citizenship by descent through great-grandmother.
- Backup route: Portugal D7 or digital nomad visa because Portugal can lead to residency/citizenship over time.
- Greece is a place the user likes and may visit, not the primary move destination.

Current milestones under this plan include duplicates and non-milestones:

- `Italian Citizenship by Descent`
- `Relocation to Portugal`
- `Move out of the country`
- `Relocate to Europe next year`
- `Europe Move`
- `Europe relocation via digital nomad visa`
- `European relocation via Italian citizenship`
- `EU Business Setup and Relocation`
- `Estonia e-residency application`
- `Relocation to Portugal`
- `International Relocation Plan`
- `Income Generation and Europe Relocation`
- `Reach first million`
- `Launch EcoDesk, Flow Force, and Clarity apps`
- `Italian Ancestry Residency`
- `Relocating abroad from the USA`

These are not clean milestones. They are overlapping plan descriptions, alternate route descriptions, exploratory questions, old extracted plans, and app/income context.

### 2. App Development Plan

Current top-level plan:

- `Three-month app development plan`

This is directionally useful, but its milestones are still noisy:

- `Launch Rex Melissa`
- `Launch three apps`
- `Three-month app development plan`
- `Rex AI Assistant Development`
- `Build and launch FlowForce app`
- `3-month app development push`
- `Project Sequence`
- `Monetize multi-user Rex version`

Problems:

- `Launch Rex Melissa` is corrupted. Melissa has nothing to do with Rex.
- `Rex AI Assistant Development` is stale because the app is being renamed to Clarity.
- `Three-month app development plan` as a milestone under the same plan is recursive and useless.
- `Build and launch FlowForce app` is either a task/checklist item or launch milestone, not a broad duplicate goal.
- `Launch three apps`, `3-month app development push`, and `Project Sequence` overlap.

The clarified app plan is:

- First app: Clarity, launching in about 2-3 weeks.
- Clarity includes the Rex personal advisor plus the financial/transactions functionality.
- Second app: EchoDesk, around mid/end of next month.
- Third app: FlowForce, by the end of the following month.
- Goal: build portfolio, enable subscriptions, support Upwork/custom project credibility, and increase odds of revenue.

### 3. Melissa Plan

Current top-level plan:

- `Ask Melissa out for dinner`

That is acceptable as one plan, but the five milestones underneath are duplicates:

- `Monday outing with Melissa`
- `Date with Melissa next week`
- `Next week date with Melissa`
- `Monday date with Melissa`
- `Next-week dinner with Melissa`

Clarified truth:

- The user already asked Melissa.
- Melissa said she would respond.
- The user thinks she is likely not interested.
- This should stay as one lightweight plan or one entity event, not five open goals.
- It should only continue if Melissa replies or something materially changes.

### 4. Income and Savings

Current records include overlapping income targets:

- `$5k monthly revenue target`
- `One-year location-independent income`
- `Reach 5k monthly income in 12 months`
- `Minimum Monthly Income Target`
- `Hit $3k/month revenue`
- `Reach $3k/month by end of year`
- `Rex and FlowForce client acquisition`
- `Launch Apps for Revenue`
- `Increase income via freelance`

Clarified truth:

- User has not reliably hit $3k/month yet.
- Goal: reach around $3k/month by the end of this year.
- Then reach around $5k/month, or roughly $5k profit/month, as the practical move-out threshold.
- Revenue can come from subscriptions, Upwork, custom projects, or any mix of Clarity/EchoDesk/FlowForce.
- This income target belongs under the move-out plan as a prerequisite, not duplicated across multiple plans.

### 5. Person Memory

Current production people data still contains a false Stephanie fact:

- `Stephanie`
- Summary: `got fired at the beginning of this year`
- Relationship: `Laura's friend who lives with her`

Clarified truth:

- Lara/Laura is the kitchen supervisor who got fired at the beginning of this year.
- Stephanie is her friend who lives with her.
- Stephanie quit about a month ago.
- Stephanie was not fired at the beginning of this year.

This proves correction workflow is incomplete. It updated one record but left the false fact active on another record.

## Root Causes

### Root Cause 1 - Memory Extraction Saves Without User Confirmation

File:

- `backend/app/services/chat_service.py`
- `backend/app/services/memory_extraction_service.py`

The chat service saves user messages, gets the assistant response, then runs memory extraction. In streaming mode, extraction is scheduled in the background after the response.

This means:

- The user can see an answer before memory writes finish.
- The assistant can claim cleanup happened without verified final state.
- Structured memory can be created without explicit confirmation.

This conflicts with the desired behavior: any durable memory write should be saved only after the user confirms it.

### Root Cause 2 - Extraction Reads the Assistant Response Too

File:

- `backend/app/services/memory_extraction_service.py`

The extraction payload includes both:

- `user_message`
- `assistant_response`

That is dangerous. If the assistant says "Done. All duplicates removed", the extraction model can treat that as truth even if the database did not actually change.

Rule needed:

> Durable memory must be extracted from user-stated facts and confirmed backend operations, not from assistant claims.

### Root Cause 3 - Plan Intelligence Routes Noise Into Milestones

File:

- `backend/app/services/plan_intelligence_service.py`
- `backend/scripts/consolidate_plans.py`

The plan intelligence layer prevented some duplicate top-level plans, but its fallback behavior often creates a milestone under an existing plan.

That is why top-level plans dropped while milestone count grew.

The current behavior is:

- Duplicate top-level plan found.
- Archive duplicate plan.
- Create a milestone from it.

That preserves the duplicate content in a different bucket.

Correct behavior should be:

- If the duplicate is just alternate wording, archive it without creating anything.
- If it contains useful new detail, merge the detail into the existing plan description or checklist.
- Only create a milestone when it is a measurable achievement or real checkpoint.

### Root Cause 4 - Milestones Are Semantically Wrong

Files:

- `backend/app/models/plan.py`
- `backend/app/services/memory_extraction_service.py`
- `lib/features/accountability/presentation/pages/accountability_page.dart`

Milestones currently behave like generic sub-goals. That is too broad.

For this app, the user expects milestones to feel like medals/trophies:

- `Clarity launched`
- `EchoDesk launched`
- `FlowForce launched`
- `$3k/month reached`
- `$5k/month profit reached`
- `Italian citizenship application submitted`

Milestones should not be used for:

- raw plan descriptions
- alternate phrasings
- exploratory questions
- vague strategy
- repeated dating logistics
- assistant-generated summaries

Tasks/checklists should handle concrete next actions. Entity events should handle historical/context facts.

### Root Cause 5 - Duplicate Detection Ignores Milestones

File:

- `backend/app/routes/accountability.py`

`_duplicate_warnings()` only checks:

- plans
- rules

It does not check:

- milestones
- commitments
- entities
- entity events

That is why the UI can show `duplicate_warning_count: 0` while also showing five Melissa duplicate milestones and many relocation duplicates.

### Root Cause 6 - Correction Service Is String-Replacement Based

File:

- `backend/app/services/memory_correction_service.py`

The correction service handles simple patterns like "replace X with Y" and "remove X". It does not deeply understand multi-entity corrections like:

> Lara got fired. Stephanie did not get fired. Stephanie quit a month ago.

That requires a truth rewrite across multiple records:

- update Lara summary
- update Stephanie summary
- remove false Stephanie fired statement
- add Stephanie quit event
- verify no active records still contain the false fact

The current correction system can update some matching records but miss related false facts.

### Root Cause 7 - The UI Shows Internal Memory Components As User Goals

File:

- `lib/features/accountability/presentation/pages/accountability_page.dart`

The UI renders all open milestones under each plan. That exposes internal memory fragments as if they are clean user-facing goals.

The Accountability page should show:

- top-level plan title
- plan description/instructions
- current active tasks
- a small progress summary
- completed milestone badges/trophies
- duplicate warnings if memory is dirty

It should not show every open extracted milestone by default.

## Recommended Target Memory Model

### Memory Layers

Rex should separate these layers:

1. **Conversation log**
   - Raw user/assistant messages.
   - Always saved for conversation continuity.
   - Not treated as durable truth by itself.

2. **Pending memory candidates**
   - Proposed facts, entities, plans, tasks, milestones, and corrections.
   - Not active until confirmed.
   - User can approve, edit, or reject.

3. **Canonical entities**
   - People, apps, places, organizations, projects.
   - Updated carefully.
   - Corrections require verification that stale facts are gone.

4. **Entity events**
   - Historical events or relationship changes.
   - Example: "Stephanie quit about a month ago."
   - These do not become plans.

5. **Top-level plans**
   - Few, durable, user-confirmed.
   - Should be manually confirmed before creation.

6. **Tasks/checklists**
   - Concrete actions the user can mark done.
   - Visible in Accountability.

7. **Milestones**
   - Achievement badges/checkpoints.
   - Usually hidden until completed or shown as progress targets.
   - Not a dumping ground for extracted plan fragments.

### Confirmation Policy

Recommended default:

- Conversation messages: save automatically.
- Structured memory candidates: save as pending only.
- Plans: require confirmation.
- Milestones: require confirmation unless generated by an explicit checklist template the user approved.
- Commitments/tasks: require confirmation unless the user explicitly says "remind me", "track this", "add this task", or "I commit to".
- Entity summaries: require confirmation for relationship/person corrections.
- Entity events: can be pending-confirmation by default.
- Rules: require confirmation unless the user phrases it as a direct rule.

No assistant response should say "fixed", "saved", "archived", or "removed" unless the backend returns verified applied changes.

## Recommended Clean Target State

### Plan 1 - Move Out Of The Country Next Year

Possible title:

- `Move out of the country next year`

Description:

- Primary path is Italian citizenship by descent through great-grandmother.
- If law changes or eligibility blocks that route, fallback is Portugal D7 or digital nomad visa.
- Portugal is the primary relocation target because it can lead to residency/citizenship over time.
- Greece is a place to visit, not the current primary destination.
- Income requirement is around $3k/month by end of year, then about $5k/month or $5k profit/month before moving.
- Income can come from Clarity, EchoDesk, FlowForce subscriptions, Upwork, or custom projects.

Visible tasks/checklist:

- Verify Italian citizenship eligibility under current law.
- Gather ancestry/citizenship documents.
- Save or secure initial lawyer/application funds.
- Research Portugal D7/digital nomad requirements.
- Track monthly revenue toward $3k/month.
- Track monthly profit/runway toward $5k/month or move threshold.

Milestones/badges:

- `Italian citizenship eligibility confirmed`
- `Italian citizenship application submitted`
- `$3k/month revenue reached`
- `$5k/month profit reached`
- `Portugal visa fallback ready`
- `Move date selected`

Archive or hide as internal:

- `Relocate to Greece`
- `Relocate to Europe next year`
- `Europe Move`
- `Move out of the country` as a duplicate milestone if it is the top-level plan
- `Europe relocation via digital nomad visa`
- `European relocation via Italian citizenship`
- `International Relocation Plan`
- `Relocating abroad from the USA`
- `Reach first million`

### Plan 2 - Launch And Monetize Clarity, EchoDesk, And FlowForce

Possible title:

- `Launch and monetize Clarity, EchoDesk, and FlowForce`

Description:

- Launch Clarity first in about 2-3 weeks.
- Clarity is the new app name and includes the Rex personal advisor plus the financial/transaction access functionality.
- Launch EchoDesk around mid/end of next month.
- Launch FlowForce by the end of the following month.
- Use the launched apps for subscriptions, portfolio proof, Upwork credibility, and custom project opportunities.

Visible tasks/checklist:

- Prepare Clarity release build.
- Finish Clarity transaction/budget functionality.
- Prepare Clarity subscription/testing path.
- Define EchoDesk MVP scope.
- Define FlowForce MVP scope.
- Add portfolio/demo material for Upwork.

Milestones/badges:

- `Clarity launched`
- `EchoDesk launched`
- `FlowForce launched`
- `First subscription user`
- `First Upwork/custom client from portfolio`

Archive or hide as internal:

- `Launch Rex Melissa`
- `Rex AI Assistant Development`
- `Three-month app development plan` as milestone
- `3-month app development push`
- `Project Sequence`
- `Monetize multi-user Rex version`
- `Build and launch FlowForce app` if replaced by the cleaner FlowForce launch badge/task set

### Plan 3 - Melissa Follow-Up

Possible title:

- `Melissa follow-up`

Description:

- User already asked Melissa out.
- Melissa said she would tell him her response.
- User thinks she is likely not interested.
- Continue only if she responds or there is a meaningful new interaction.

Visible tasks/checklist:

- None unless there is a real next action.

Milestones/badges:

- None needed right now.

Archive:

- `Monday outing with Melissa`
- `Date with Melissa next week`
- `Next week date with Melissa`
- `Monday date with Melissa`
- `Next-week dinner with Melissa`

These are duplicate phrasings of the same situation.

## Required Implementation Fixes

### P0 - Stop Auto-Saving Structured Memory

Add a pending memory queue/table.

Suggested table:

- `memory_candidates`

Fields:

- `id`
- `candidate_type`
- `payload`
- `source_conversation_id`
- `source_message_id`
- `status`: `pending`, `approved`, `rejected`, `applied`
- `risk_level`: `low`, `medium`, `high`
- `reason`
- `created_at`
- `updated_at`

All structured extraction should write to this table first.

### P0 - User Confirmation Before Structured Writes

Add an approval endpoint:

- `POST /memory-candidates/{id}/approve`
- `POST /memory-candidates/{id}/reject`
- `PATCH /memory-candidates/{id}`

Only approval applies the write to:

- entities
- entity events
- plans
- milestones
- commitments
- rules

### P0 - Extract From User Message Only

Change extraction payload so durable facts come from the user message only.

Assistant response may be included only as non-authoritative context and must never be saved as a source of truth.

### P0 - Verified Write Summary

The assistant may only say memory was changed if the backend returns:

- record type
- record id
- action
- before/after summary
- verification result

If verification fails, Rex must say:

- "I tried, but it did not apply."
- "Here is what is still wrong."

### P0 - Correction Verification Pass

After any correction, run a verification query across:

- long-term memory
- entities
- entity events
- plans
- milestones
- commitments
- rules

Example verification:

- Query: `"Stephanie got fired"`
- Expected: no active records contain that claim.

If any active record still contains the stale claim, do not tell the user it was fully fixed.

### P1 - Redefine Milestones

Milestones should be achievement checkpoints, not extracted sub-plans.

Add stricter rules:

- Title should usually be past-tense/completion-oriented or a measurable target.
- Do not create milestone from a plan title.
- Do not create milestone if the title is semantically equivalent to parent plan.
- Do not create milestone for exploratory questions.
- Do not create milestone for assistant advice.
- Do not create milestone for duplicate date logistics.

### P1 - Add Milestone Duplicate Detection

Update `backend/app/routes/accountability.py`.

Duplicate warnings should include:

- milestones within the same plan
- commitments within the same plan/milestone
- entity summaries with conflicting facts

### P1 - Replace Consolidation Script Behavior

Current consolidation behavior often creates a milestone from every archived duplicate plan.

New rule:

- Archive duplicate if it adds no unique fact.
- Merge unique facts into parent plan description or metadata.
- Create a task only if it is concrete.
- Create a milestone only if it is an achievement checkpoint.

### P1 - UI Should Not Show Internal Memory Noise

Update Accountability UI:

- Show plan description/instructions prominently.
- Show current tasks/checklist.
- Show milestone badges separately.
- Hide raw open milestones by default.
- Add a "Memory cleanup needed" warning if duplicate milestones exist.

### P2 - Current Data Cleanup

After the preventive changes are in place, run a one-time cleanup to:

- Rename relocation plan away from Greece.
- Update Stephanie.
- Collapse Melissa milestones.
- Collapse income target milestones.
- Collapse app plan milestones.
- Archive exploratory/non-plan items like `Reach first million`.

Do not run another cleanup before the preventive fixes, or the system may recreate the same mess.

## Recommended Next Build Order

1. Add pending memory candidates and confirmation flow.
2. Stop extracting durable memory from assistant responses.
3. Add correction verification.
4. Redefine milestone creation rules.
5. Add milestone duplicate warnings.
6. Update Accountability UI to show tasks and plan descriptions instead of all open milestones.
7. Run the current-data cleanup once.

## Bottom Line

The main architecture should change from:

> chat turn -> extraction -> direct write -> assistant says fixed

to:

> chat turn -> candidate extraction -> user confirmation -> verified write -> assistant reports exact applied changes

That is the only way Rex becomes trustworthy enough for personal memory.
