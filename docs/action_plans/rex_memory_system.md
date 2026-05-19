# Rex Memory System

## Goal

Build Rex into a real long-term personal co-pilot with layered, accurate, and useful memory.

The current system already has the foundation: generic long-term memory, structured entities, rules, plans, milestones, commitments, accountability signals, prompt injection, and Flutter views. The next phase should not restart from scratch. It should harden the memory system so corrections replace stale truth, people and plans become first-class objects, and retrieval gives Rex the right context at the right moment.

## Current Problem

Rex can save memories, but the quality is not reliable enough for daily use yet.

Main gaps:

- Flat memories still compete with structured records.
- Corrections can create new rows without fully replacing stale rows.
- A person can exist as text in `long_term_memory` without a matching `entities` row.
- Plans can keep old names or wrong assumptions after the user corrects them.
- Retrieval can find a related plan but miss the corrected entity or location context.
- The UI shows memory rows, but the user needs a clearer map of what Rex knows.

Example failure:

- Old memory: `I am planning to ask Al out for dinner...`
- Correction: `Her name is Melissa, not Al.`
- Desired result: update/deactivate the stale `Al` memory, create/update the `Melissa` person entity, link the dating plan to Melissa, and retrieve only the corrected version later.

## Memory Layers

Rex should treat memory as separate layers with different lifetimes and retrieval rules.

### Short-Term Memory

Source: current chat turn and recent conversation messages.

Use for:

- Immediate context
- Pronouns and references like "she", "that plan", "tomorrow"
- Live voice call continuity

Storage:

- `conversations`
- `messages`

Retrieval:

- Recent messages by conversation
- Last N turns, capped by prompt budget

### Medium-Term Memory

Source: recent events, entity events, open commitments, active plan updates.

Use for:

- What happened recently
- Follow-ups
- Fresh corrections
- Things that should affect the next few days or weeks

Storage:

- `entity_events`
- `plan_milestones`
- `commitments`
- high-recency `long_term_memory`

Retrieval:

- Recency plus relevance
- Upcoming due dates
- Mentioned people/plans/rules

### Long-Term Memory

Source: stable facts, preferences, rules, people, plans, goals, and identity-level context.

Use for:

- Persistent personal facts
- People Rex should remember
- Rules Rex should enforce
- Big goals and life plans
- Preferences and communication style

Storage:

- `entities`
- `personal_rules`
- `plans`
- `commitments`
- stable `long_term_memory`

Retrieval:

- Entity resolution
- Rule/plan/commitment status
- Importance
- Explicit user message relevance

## Updated Supabase Schema

The current schema already has the core tables. The v2 schema should preserve them and add a few fields that improve correction, linking, confidence, and auditability.

### Existing Core Tables

- `conversations`
- `messages`
- `long_term_memory`
- `entities`
- `entity_events`
- `personal_rules`
- `plans`
- `plan_milestones`
- `commitments`
- `voice_turns`

### Recommended Additions

#### `long_term_memory`

Add:

```sql
alter table public.long_term_memory
  add column if not exists superseded_by uuid references public.long_term_memory(id) on delete set null,
  add column if not exists confidence numeric not null default 0.75 check (confidence between 0 and 1),
  add column if not exists correction_group text,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists long_term_memory_correction_group_idx
  on public.long_term_memory (correction_group)
  where correction_group is not null;
```

Purpose:

- `superseded_by`: points stale memory to its replacement.
- `confidence`: lets Rex avoid overclaiming uncertain extracted data.
- `correction_group`: groups old and new versions of the same claim.
- `metadata`: stores extraction hints without schema churn.

#### `entities`

Add:

```sql
alter table public.entities
  add column if not exists canonical_source text not null default 'extracted',
  add column if not exists confidence numeric not null default 0.75 check (confidence between 0 and 1),
  add column if not exists superseded_by uuid references public.entities(id) on delete set null;

create index if not exists entities_aliases_gin_idx
  on public.entities using gin (aliases);
```

Purpose:

- Supports people like Melissa as first-class records.
- Allows alias lookup and correction.
- Lets Rex avoid treating uncertain guesses as confirmed truth.

#### `entity_events`

Add:

```sql
alter table public.entity_events
  add column if not exists replaces_event_id uuid references public.entity_events(id) on delete set null,
  add column if not exists confidence numeric not null default 0.75 check (confidence between 0 and 1);
```

Purpose:

- Lets a correction replace a previous event without deleting history.

#### `plans`

Add:

```sql
alter table public.plans
  add column if not exists primary_entity_id uuid references public.entities(id) on delete set null,
  add column if not exists confidence numeric not null default 0.75 check (confidence between 0 and 1);

create index if not exists plans_primary_entity_idx
  on public.plans (primary_entity_id);
```

Purpose:

- Links a dating plan directly to Melissa instead of burying her name in text.

#### `memory_corrections`

Add a small audit table for explicit corrections.

```sql
create table if not exists public.memory_corrections (
  id uuid primary key default gen_random_uuid(),
  correction_type text not null check (
    correction_type in (
      'entity_name',
      'entity_relationship',
      'plan_detail',
      'rule_detail',
      'commitment_detail',
      'location',
      'preference',
      'other'
    )
  ),
  old_value text,
  new_value text not null,
  target_table text,
  target_id uuid,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_message_id uuid references public.messages(id) on delete set null,
  applied boolean not null default false,
  confidence numeric not null default 0.9 check (confidence between 0 and 1),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists memory_corrections_target_idx
  on public.memory_corrections (target_table, target_id);
```

Purpose:

- Gives Rex an audit trail: what was wrong, what replaced it, and whether it was applied.
- Helps debug user reports like "I already corrected this."

## Main Models

### Entity

Represents a person, place, organization, job, project, topic, object, or other named thing.

Key fields:

- `id`
- `entity_type`
- `display_name`
- `normalized_name`
- `aliases`
- `relationship`
- `summary`
- `importance`
- `status`
- `active`
- `confidence`
- `superseded_by`
- `metadata`

Person examples:

- `Melissa`
- `coworker from work`
- aliases: `["the girl from work", "my next week date"]`
- relationship: `dating_interest`

### Entity Event

Represents something that happened with or about an entity.

Key fields:

- `entity_id`
- `event_type`
- `title`
- `content`
- `occurred_at`
- `importance`
- `confidence`
- `replaces_event_id`

Examples:

- `User invited Melissa to dinner.`
- `Melissa has Monday off.`
- `User corrected that the person is Melissa, not Al.`

### Personal Rule

Represents a rule Rex should enforce.

Key fields:

- `rule_type`
- `title`
- `rule_text`
- `trigger_keywords`
- `enforcement_style`
- `priority`
- `status`
- `starts_at`
- `ends_at`

Examples:

- `No Uber unless it is unsafe to walk.`
- `Do not order DoorDash this week.`
- `Keep groceries under $80.`

### Plan

Represents a larger active goal.

Key fields:

- `plan_type`
- `title`
- `description`
- `desired_outcome`
- `primary_entity_id`
- `priority`
- `status`
- `start_date`
- `target_date`

Examples:

- `Ask Melissa out for dinner`
- `Move out of the country`
- `Increase monthly income`

### Plan Milestone

Represents a checkpoint or deadline inside a plan.

Key fields:

- `plan_id`
- `title`
- `description`
- `milestone_type`
- `target_date`
- `status`
- `priority`

Examples:

- `Ask Melissa by Monday`
- `Pick restaurant`
- `Confirm dinner time`

### Commitment

Represents something the user said they will do.

Key fields:

- `commitment_type`
- `title`
- `commitment_text`
- `plan_id`
- `entity_id`
- `due_at`
- `status`
- `priority`

Examples:

- `Text Melissa tomorrow`
- `Restart backend after deploy`
- `Review action plan 4 tonight`

### Memory Correction

Represents an explicit correction.

Key fields:

- `correction_type`
- `old_value`
- `new_value`
- `target_table`
- `target_id`
- `applied`
- `confidence`

Examples:

- `old_value = Al`, `new_value = Melissa`
- `correction_type = entity_name`
- `target_table = plans`

## Service Layer Design

### `MemoryService`

Role:

- Low-level Supabase access.
- No business logic beyond request shaping and error handling.

Responsibilities:

- CRUD for `long_term_memory`
- CRUD for structured memory tables
- Narrow methods for query patterns used by services
- No direct Grok calls

### `EntityService`

Role:

- Resolve, deduplicate, update, and retrieve entities.

Responsibilities:

- Normalize names
- Match aliases
- Merge duplicate people
- Add entity events
- Resolve phrases like "the girl from work" to a known person when confidence is high
- Track corrections like "not Al, Melissa"

### `RuleService`

Role:

- Manage personal rules.

Responsibilities:

- Create/update/deactivate rules
- Deduplicate similar rules
- Retrieve active rules relevant to the current message
- Provide trigger keyword matching for accountability

### `PlanService`

Role:

- Manage plans and milestones.

Responsibilities:

- Create/update/deactivate plans
- Link plans to entities
- Update stale plan details when corrected
- Retrieve active and relevant plans
- Track target dates and milestones

### `CommitmentService`

Role:

- Manage commitments and follow-ups.

Responsibilities:

- Create/update/deactivate commitments
- Link commitments to plans and entities
- Detect completion language
- Retrieve overdue and upcoming commitments

### `MemoryExtractionService`

Role:

- Convert conversation turns into memory candidates.

Responsibilities:

- Extract long-term notes
- Extract structured entities/rules/plans/commitments
- Detect correction intent
- Apply corrections before creating new rows
- Reject low-value or uncertain candidates
- Never block chat response if extraction fails

### `PromptService`

Role:

- Build compact prompt context.

Responsibilities:

- Inject current time and timezone
- Inject relevant structured memory
- Inject accountability signals
- Avoid prompt overload
- Prefer corrected/current truth over stale rows

### `AccountabilityService`

Role:

- Compare current behavior against rules, commitments, and plans.

Responsibilities:

- Detect rule violations
- Detect missed commitments
- Detect plan drift
- Detect repeated patterns
- Return structured accountability signals

## Extraction Prompt Improvements

The memory extraction prompt should explicitly separate "new fact" from "correction."

### Required Output Shape

The extractor should emit JSON with these top-level keys:

```json
{
  "long_term_memories": [],
  "entities": [],
  "entity_events": [],
  "personal_rules": [],
  "plans": [],
  "plan_milestones": [],
  "commitments": [],
  "corrections": []
}
```

### Correction Candidate Shape

```json
{
  "correction_type": "entity_name",
  "old_value": "Al",
  "new_value": "Melissa",
  "target_hint": "next-week dinner date plan",
  "confidence": 0.95,
  "rationale": "User explicitly said her name is Melissa, not Al."
}
```

### Extraction Rules

The prompt should instruct the model:

- If the user says something was wrong, output a `corrections` item.
- Do not create both stale and corrected versions.
- If a person is named, create or update an entity.
- If a name correction affects a plan, link the corrected entity to the plan.
- If confidence is low, store an event/note but do not overwrite a stable entity.
- Prefer exact user corrections over inferred context.
- Keep memory text concise and reusable.

### Example

User:

```text
Her name is Melissa, not Al. The plan is still dinner Monday near my place.
```

Expected extraction:

```json
{
  "entities": [
    {
      "entity_type": "person",
      "display_name": "Melissa",
      "aliases": ["next-week dinner date", "coworker from work"],
      "relationship": "dating_interest",
      "summary": "Melissa is the person the user is planning to ask out for dinner."
    }
  ],
  "entity_events": [
    {
      "event_type": "relationship_update",
      "content": "User corrected that the dinner plan is with Melissa, not Al."
    }
  ],
  "plans": [
    {
      "plan_type": "dating",
      "title": "Ask Melissa out for dinner",
      "desired_outcome": "Dinner date with Melissa",
      "status": "active"
    }
  ],
  "corrections": [
    {
      "correction_type": "entity_name",
      "old_value": "Al",
      "new_value": "Melissa",
      "target_hint": "next-week dinner plan",
      "confidence": 0.95
    }
  ]
}
```

## Entity Resolution Strategy

Entity resolution should be deterministic first, model-assisted later.

### Matching Order

1. Exact normalized name match.
2. Alias match.
3. Correction match: `old_value` appears in stale record and `new_value` appears in current message.
4. Plan/entity relationship match: user mentions "that date", "her", "the girl from work".
5. Fuzzy text match against recent relevant records.
6. If still ambiguous, store an entity event or ask the user.

### Merge Rules

Merge/update when:

- Same normalized name and entity type.
- Alias points to existing entity.
- User explicitly says X is now Y.
- New details clearly refer to the same person/plan.

Do not merge when:

- Two different people share similar names.
- The user says they are different people.
- Confidence is low and no alias exists.

### Correction Behavior

When a correction is detected:

1. Find stale long-term memories, entities, entity events, plans, and commitments that contain `old_value`.
2. Prefer records connected to the current conversation or target hint.
3. Update the best target in place when safe.
4. Mark extra stale records inactive or superseded.
5. Add a `memory_corrections` row.
6. Add an entity event describing the correction.
7. Re-run retrieval using the corrected value.

## Retrieval Strategy

Retrieval should be layered and budgeted.

### Per Chat Turn

Inputs:

- Current user message
- Conversation ID
- Current time context
- Recent messages
- Active long-term memories
- Structured memory candidates

Process:

1. Extract names, aliases, dates, rule keywords, and plan keywords from the message.
2. Fetch recent conversation history.
3. Fetch relevant long-term memories.
4. Fetch matching entities and recent entity events.
5. Fetch active personal rules matching keywords.
6. Fetch active plans matching people, keywords, or deadlines.
7. Fetch open commitments linked to matched plans/entities.
8. Fetch accountability signals.
9. Rank context by relevance, recency, importance, and status.
10. Build a compact prompt context.

### Prompt Priority

Highest priority:

- Current user message
- Explicit corrections
- Active rules likely relevant now
- Mentioned person/entity details
- Active plan tied to the user message
- Open commitments due soon or overdue

Medium priority:

- Recent entity events
- Recent memories from same conversation
- Preferences related to the topic

Low priority:

- Old generic facts
- Unrelated memories
- Superseded or inactive records

### Prompt Format

Use compact sections:

```text
Current Time:
- User timezone: America/New_York
- Local date/time: ...

Relevant People:
- Melissa: dating interest; user plans to ask her out for dinner Monday. Corrected from Al.

Relevant Plans:
- Ask Melissa out for dinner: active; desired outcome: dinner date; target: Monday.

Personal Rules:
- ...

Open Commitments:
- ...

Important Notes:
- User lives in Massachusetts.
```

## Flutter UI Map

The Memory screen should show layers, not only generic memory types.

Top-level tabs:

- Notes
- People
- Rules
- Plans
- Commitments

Notes subfilters:

- All
- Facts
- Preferences
- Events

People view:

- Name
- Relationship
- Summary
- Aliases
- Recent events
- Connected plans

Plans view:

- Title
- Desired outcome
- Status
- Target date
- Linked person
- Milestones

Rules view:

- Rule
- Trigger keywords
- Enforcement style
- Status

Commitments view:

- Commitment
- Due date
- Status
- Linked plan/person

## Implementation Order

This order assumes a solo developer and prioritizes correctness over broad features.

### Phase 1 - Stabilize Correction Handling

Goal: Stop wrong memory from surviving after explicit correction.

Tasks:

- Add `memory_corrections` schema.
- Add `superseded_by`, `confidence`, `correction_group`, and `metadata` fields where needed.
- Expand correction extraction.
- Update stale long-term memory instead of only appending new rows.
- Deactivate or supersede duplicate stale rows.
- Add tests for `Al -> Melissa`, location correction, and plan detail correction.

Verification:

- `PYTHONPATH=backend python3 -m pytest -q tests/test_memory_extraction.py tests/test_memory_retrieval.py`

### Phase 2 - Make People First-Class

Goal: A person should not live only as text in a generic memory row.

Tasks:

- Improve person extraction.
- Add alias handling for "girl from work", "my date", "Melissa".
- Link entity events to people.
- Backfill obvious people from existing long-term memories.
- Add retrieval by person name and alias.

Verification:

- Ask "Do you remember Melissa?" and Rex should answer from `entities` plus related events, not generic memory guesses.

### Phase 3 - Link Plans to People

Goal: Plans should update when the person or detail changes.

Tasks:

- Add `primary_entity_id` to plans.
- Link dating, work, immigration, finance, and health plans to relevant entities.
- Update plan title/description when corrected.
- Add plan correction tests.

Verification:

- Correcting "Al" to "Melissa" updates the active dating plan and prompt context.

### Phase 4 - Improve Retrieval Ranking

Goal: Rex should retrieve the right context without overloading the prompt.

Tasks:

- Add a retrieval scoring function.
- Penalize inactive/superseded records.
- Boost exact entity/rule/plan matches.
- Boost recent corrections.
- Cap each prompt section.

Verification:

- Prompt includes Melissa and Massachusetts when relevant.
- Prompt excludes stale Al memory after correction.

### Phase 5 - Improve UI Visibility

Goal: The founder should see what Rex knows and why.

Tasks:

- Add Memory layer tabs.
- Show People, Rules, Plans, Commitments separately.
- Add edit/deactivate actions for structured records.
- Show correction history where useful.
- Add "linked to" metadata for plans and people.

Verification:

- The user can open Memory and see Melissa as a person, the dating plan as a plan, and old Al memory inactive/superseded.

### Phase 6 - Manual Real-Data Validation

Goal: Prove the memory system works with actual daily usage.

Test flow:

1. Tell Rex a person exists.
2. Add a plan with that person.
3. Correct the person's name.
4. Ask Rex what it remembers.
5. Confirm the old name is not treated as current truth.
6. Create a personal rule.
7. Violate the rule.
8. Confirm accountability signal appears.
9. Check Memory UI layers.
10. Check Supabase rows.

Verification:

- `PYTHONPATH=backend python3 -m pytest -q tests`
- `flutter analyze`
- `flutter test`
- Manual phone test against VPS.

## Quality Bar

The memory system is good enough when:

- Rex remembers people as people, not just text snippets.
- Rex updates stale facts after explicit correction.
- Rex does not keep arguing from old wrong memory.
- Rex can connect plans to people and dates.
- Rex can explain what it knows without hallucinating hidden access.
- The user can inspect and correct memory from the UI.
- Tests catch duplicated stale memory, failed correction, and bad retrieval.

## Non-Goals For This Phase

Do not add these yet:

- Full semantic vector search.
- Multi-user auth/RLS complexity.
- Public memory sharing.
- Heavy background jobs.
- Complex graph database migration.

The realistic path is to make the current Supabase + FastAPI + Flutter system reliable first.
