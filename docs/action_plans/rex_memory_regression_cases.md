# Rex Memory Discipline Regression Cases

These cases capture the failure modes that created plan spam and entity drift.
They should stay covered by automated tests before changing memory extraction,
discipline, correction, or accountability code.

## Corrected Entity Names
- Input: "It is Melissa, not Al."
- Expected: active Melissa entity is updated or created; stale Al/AI entity is archived or marked obsolete.
- Never: keep Al/AI as the active current person for the date plan.

## Duplicate Dating Plan
- Input: "Date with Melissa next week" when "Ask Melissa out for dinner" already exists.
- Expected: update the existing Melissa plan or add a milestone/checklist item under it.
- Never: create another top-level Melissa dating plan.

## Overlapping Income Plans
- Input: "$5k/month revenue", "$600 savings", or "location-independent income" when "Relocate to Europe next year" exists.
- Expected: attach as milestones/tasks under the Europe relocation plan when related.
- Never: create many separate top-level finance plans that describe the same larger goal.

## App/Project Name Drift
- Canonical names: EchoDesk and FlowForce.
- Wrong variants: Flow, Flowfirst, Flowforte, Echotask, EchoTask.
- Expected: rewrite wrong variants to canonical active entities.
- Never: save wrong variants as active project names after correction.

## Duplicate Rules
- Input: another "No Uber or DoorDash" or paycheck savings rule.
- Expected: update the existing active rule.
- Never: create multiple active copies of the same rule.

## Task Misclassified As Plan
- Input: "Email the first FlowForce lead tomorrow."
- Expected: commitment/checklist item under the relevant app/work plan.
- Never: create a top-level plan for a single next action.

## Correction Archives Stale Record
- Input: "Delete the old one; the correct one is X."
- Expected: stale record is archived/deactivated and the correct record is updated.
- Never: leave both stale and corrected records active with equal authority.
