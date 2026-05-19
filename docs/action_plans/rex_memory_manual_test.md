# Rex Memory Manual Test

This checklist validates Rex memory against real daily-use behavior, not only unit tests. Run it after deploying backend changes, applying Supabase migrations, and installing the latest app build on the phone.

Use one realistic conversation. Do not seed fake memories unless the step explicitly says to create a test memory through Rex.

## Preflight

**Goal:** Confirm the app and backend are using the latest deployed memory code.

**Commands:**

```bash
cd /opt/rex
git pull
source .venv/bin/activate
pip install -r backend/requirements.txt
sudo systemctl restart rex-backend
curl -s https://api.rexpilot.com/ready | python3 -m json.tool
```

**Pass criteria:**

- `/ready` returns `status: ready`.
- `time.timezone` is `America/New_York`.
- `supabase` is configured.
- The app build uses `https://api.rexpilot.com`.

## Test 1 - Explicit Person Correction

**Goal:** Rex updates wrong person memory instead of stacking another vague memory.

**Say or type:**

```text
The person for my next-week date plan is Melissa, not Al.
```

Then ask:

```text
Who is the person connected to my next-week date plan?
```

**Pass criteria:**

- Rex answers Melissa.
- Rex does not say the active plan is still with Al.
- Memory UI shows a corrected/person-related memory for Melissa.
- If the old Al memory still exists, it is inactive or clearly superseded by the Melissa correction.

**Supabase/API checks:**

```bash
curl -s "https://api.rexpilot.com/memory?limit=100&active=true" | python3 -m json.tool
curl -s "https://api.rexpilot.com/entities" | python3 -m json.tool
curl -s "https://api.rexpilot.com/plans" | python3 -m json.tool
```

Look for:

- A person/entity record for Melissa.
- A dating plan with `primary_entity_id` linked to Melissa.
- No active current-truth memory saying the plan is with Al.

## Test 2 - Location And Timezone

**Goal:** Rex uses the user's real configured timezone/location context when time or location matters.

**Say or type:**

```text
Do you remember what state I live in, and what timezone that means for me?
```

**Pass criteria:**

- Rex says Massachusetts if that memory exists.
- Rex connects Massachusetts to Eastern time / `America/New_York`.
- Rex does not say it is in CEST or Europe as the user's context.
- If it is unsure about city, it says so without ignoring the state/timezone.

## Test 3 - Plan Retrieval Through Person

**Goal:** Rex retrieves the date plan whether the user asks by person or by plan.

**Ask by person:**

```text
What do you remember about Melissa?
```

**Ask by plan:**

```text
What is my next-week date plan?
```

**Pass criteria:**

- Both questions retrieve the same dating plan context.
- Rex mentions Melissa when discussing the plan.
- Rex does not ask for the person's name again if Melissa is already stored.
- The Accountability page plan section shows the plan linked to the correct person when available.

## Test 4 - Personal Rule And Accountability Signal

**Goal:** Rex notices a likely rule violation only when a matching active rule exists.

First create a rule if one does not exist:

```text
Remember this as a personal rule: I should not order DoorDash while I am trying to control spending.
```

Then test:

```text
I ordered DoorDash again tonight.
```

**Pass criteria:**

- Rex recognizes this as a budget/food-delivery rule violation.
- Tone is direct but useful, not generic.
- Accountability page shows at least one relevant signal or active rule.
- An unrelated sentence like `I walked past a restaurant` should not trigger the DoorDash rule.

## Test 5 - Memory UI Layers

**Goal:** The app makes the memory model inspectable.

Open Memory and Accountability pages.

**Pass criteria:**

- Memory page shows flat memories under Notes/Facts/Preferences/Events.
- People layer shows Melissa as a person if she has been saved.
- Plans layer shows the dating plan.
- Accountability page shows active rules, open commitments, plan progress, and current signals.
- Empty states are calm and clear when a section has no records.

## Test 6 - Stale Active Record Check

**Goal:** Verify old wrong facts are not still treated as current truth.

Run:

```bash
curl -s "https://api.rexpilot.com/memory?limit=100&active=true" | python3 -m json.tool
curl -s "https://api.rexpilot.com/entities" | python3 -m json.tool
curl -s "https://api.rexpilot.com/plans" | python3 -m json.tool
curl -s "https://api.rexpilot.com/corrections" | python3 -m json.tool
```

**Pass criteria:**

- Current active records prefer Melissa over Al.
- Any remaining Al reference is historical, inactive, or clearly marked as corrected.
- The active plan does not have `Al` in title, description, or desired outcome.
- Correction rows show `old_value` around `al` and `new_value` around `melissa` when the correction was processed.

## Result Log

Fill this after testing.

```text
Date:
App build:
Backend commit:

Test 1 - Person correction:
Pass/Fail:
Notes:

Test 2 - Location/timezone:
Pass/Fail:
Notes:

Test 3 - Plan retrieval:
Pass/Fail:
Notes:

Test 4 - Rule/accountability:
Pass/Fail:
Notes:

Test 5 - UI layers:
Pass/Fail:
Notes:

Test 6 - Stale row check:
Pass/Fail:
Notes:

Bugs found:
Next fixes:
```
