# Rex Memory Manual Test

Use this after deploying Phase 6. The goal is to confirm Rex only shows clean,
confirmed memory and does not recreate duplicate plans or milestone noise.

## Preflight

- Run the cleanup script in dry-run first.
- Review every operation before using `--apply`.
- Confirm no pending memory candidate is applied without user confirmation.

## Commands

```bash
PYTHONPATH=backend python3 backend/scripts/cleanup_rex_brain_v2_current_data.py --dry-run --limit 500
PYTHONPATH=backend python3 backend/scripts/cleanup_rex_brain_v2_current_data.py --apply --limit 500
curl -sS 'https://api.rexpilot.com/accountability/overview?limit=100' | python3 -m json.tool
```

## Expected Accountability Shape

- Top-level plans should be few and readable.
- Relocation plan should be `Move out of the country next year`.
- App plan should be `Launch and monetize Clarity, EchoDesk, and FlowForce`.
- Melissa should be one follow-up plan, not repeated date milestones.
- Raw milestones should be hidden behind Internal memory in the mobile UI.
- Completed milestones should appear as badges.
- Pending memory candidates should appear in the Pending Memory section.

## Correction Checks

Ask Rex:

```text
What do you have saved about Stephanie?
```

Expected:

- Stephanie is Lara's friend who lives with her.
- Stephanie quit about a month ago.
- Rex must not say Stephanie got fired at the beginning of this year.

Ask Rex:

```text
What is my relocation plan?
```

Expected:

- Primary route is Italian citizenship by descent.
- Portugal D7 or digital nomad route is backup.
- Greece is visit-only, not the primary move target.
- Income gate is about $3k/month by end of year, then about $5k/month before moving.

Ask Rex:

```text
What app am I launching first?
```

Expected:

- Clarity launches first.
- Clarity contains the Rex personal advisor and financial clarity features.
- EchoDesk follows, then FlowForce.

## Duplicate Creation Check

Say:

```text
I plan to move to Portugal next year.
```

Expected:

- Rex creates or shows a pending memory candidate.
- Rex does not directly create a new duplicate plan.
- Rex asks for confirmation before saving/updating durable memory.

Say:

```text
I asked Melissa out next week.
```

Expected:

- Rex treats this as an update to the existing Melissa follow-up context.
- Rex does not create another Monday/date/dinner milestone.

## Pass Criteria

- No wrong Stephanie fired fact remains active.
- No active `Relocate to Greece` top-level plan.
- No active `Launch Rex Melissa` top-level plan.
- No active `Reach first million` milestone created from exploratory chat.
- Duplicate warnings are either zero or point to real unresolved cleanup.
