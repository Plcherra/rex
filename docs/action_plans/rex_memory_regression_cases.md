# Rex Memory Regression Cases

These are the high-value failures that should stay covered as the memory system evolves. The goal is not to test every wording. The goal is to protect the real daily-use behaviors that broke before.

## 1. Explicit Person Correction

**Scenario:** Rex has an old memory saying the date plan is with `Al`. The user later says the person is `Melissa`, not `Al` or `AI`.

**Expected behavior:**

- Create or update a `person` entity for Melissa.
- Link the relevant dating plan to Melissa.
- Mark stale flat memories as superseded or inactive.
- Record a correction audit row.
- Prompt context should prefer Melissa and exclude stale active-looking `Al` rows.

**Automated coverage:**

- `tests/test_memory_extraction.py`
- `tests/test_memory_retrieval.py`
- `tests/test_prompt_service.py`

## 2. Location And Timezone Recall

**Scenario:** The user asks Rex what time it is or says Rex is using the wrong timezone. Rex has a location memory like `I am in Massachusetts.`

**Expected behavior:**

- Prompt context includes the app timezone.
- Relevant memory retrieval can surface Massachusetts/location context.
- Rex should not answer from the VPS timezone.

**Automated coverage:**

- `tests/test_memory_retrieval.py`
- `tests/test_prompt_service.py`

## 3. Person-Linked Plans

**Scenario:** The user asks about the next-week date plan without naming the person.

**Expected behavior:**

- Retrieval can select the plan.
- Retrieval also includes the linked person.
- Prompt line labels the plan with the person when available.

**Automated coverage:**

- `tests/test_memory_retrieval.py`
- `tests/test_prompt_service.py`

## 4. Stale Duplicate Suppression

**Scenario:** Multiple long-term memories mention the same topic, but one is corrected and newer.

**Expected behavior:**

- Corrected memory gets the relevance boost.
- Superseded or inactive rows are penalized or excluded.
- Old conflicting names do not override explicit corrections.

**Automated coverage:**

- `tests/test_memory_extraction.py`
- `tests/test_memory_retrieval.py`

## 5. Structured UI Corrections

**Scenario:** The Memory screen shows an incorrect person, rule, plan, or commitment.

**Expected behavior:**

- User can edit structured records.
- User can deactivate structured records.
- The UI exposes enough identifiers and linked record hints to understand what Rex is tracking.

**Automated coverage:**

- `flutter analyze`
- `flutter test`

## 6. Safe Backfill

**Scenario:** Existing flat memories need to become structured records after the schema is already live.

**Expected behavior:**

- Backfill is never automatic on startup.
- Dry-run is the default mode.
- Ambiguous names like `Al` or `AI` are skipped unless corrected to a clear name.
- Existing structured rows are merged through service-layer dedupe.

**Automated coverage:**

- `tests/test_structured_memory_backfill.py`

## Validation Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests
flutter analyze
flutter test
```

## Manual Checks Before Deploy

1. Ask Rex: `Do you remember where I live?`
2. Ask Rex: `What date plan am I talking about for next week?`
3. Correct a person name and verify the old name stops appearing.
4. Open Memory and verify People, Plans, Rules, and Commitments are readable.
5. Open Accountability and verify active rules/plans are not duplicated.
