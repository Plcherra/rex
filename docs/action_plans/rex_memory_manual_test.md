# Rex Memory Discipline Manual Test

Run these prompts through the mobile app after deploying memory discipline changes.
After each prompt, refresh Memory and Accountability.

## 1. New Top-Level Plan
Prompt:
`I want to relocate to Europe next year and build enough remote income to make it realistic.`

Expected:
- One active top-level plan exists for Europe relocation.
- Accountability shows it as a primary plan.

## 2. Related Update
Prompt:
`For the Europe move, I need to reach $5k/month and save at least $600/month.`

Expected:
- No new top-level finance plan if the Europe plan already exists.
- The income/savings items appear as milestones or checklist items under the Europe plan.

## 3. Correction
Prompt:
`Correction: it is EchoDesk, not Echotask. Delete the wrong name going forward.`

Expected:
- EchoDesk remains canonical.
- Echotask does not remain as an active project name.
- Rex briefly says what was updated or archived.

## 4. Duplicate Goal
Prompt:
`Add a plan to make $5k/month from my apps.`

Expected:
- Rex attaches it to the existing Europe/work plan if related.
- No duplicate top-level "$5k" plan is created.

## 5. Entity Spelling Fix
Prompt:
`Her name is Melissa, not Al. The date plan is with Melissa.`

Expected:
- Melissa is the active person.
- Al/AI is not the active person for that plan.
- The date plan points to Melissa or says Melissa clearly.

## 6. Merge Request
Prompt:
`Merge the duplicate Melissa date plans into one clean plan.`

Expected:
- One active Melissa dating plan remains.
- Older duplicates are archived or converted to milestones.
- Rex summarizes the cleanup.

## 7. Accountability Review
Prompt:
`Review my accountability context.`

Expected:
- Rex references a small number of high-level plans.
- Accountability screen shows top-level plans with nested milestones/tasks.
- Rules and signals remain separate from plans.
