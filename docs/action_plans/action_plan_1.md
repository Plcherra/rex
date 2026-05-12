# Action Plan 1 - Time-Aware Prompt Foundation

## Goal
Make every Rex response aware of current time, session gaps, memory ages, and the founder-specific direct personality.

## Why This Matters (Personal Context)
This is the foundational step for turning Rex into a real daily co-pilot. The founder talks to Rex while walking (often at night or after long gaps) and expects it to understand that “last night has passed,” remember promises like “I’ll work out tomorrow morning,” and give direct accountability on budget rules, dating context, immigration plans, etc. Without strong time awareness, Rex will feel like a generic chatbot that forgets real life flows.

## Key Deliverables
- `backend/app/services/time_context_service.py`
- `backend/app/services/prompt_service.py`
- Refactor `backend/app/services/chat_service.py` so prompt assembly is centralized
- Inject server time, timezone, last-message delta, memory ages, and current conversation metadata into every Grok call
- Strengthen Rex personality prompt for founder-first directness and accountability
- Add backend tests for time-context injection and prompt shape

## Estimated Time
2-4 focused days (solo founder pace)

## Dependencies
Existing chat service, message timestamps in Supabase, and memory retrieval logic.

## Checklist (7-10 Actionable Steps)

1. **Audit current prompt assembly and timestamp data flow**
   - Exact files to create or modify: `backend/app/services/chat_service.py`, `backend/app/services/ai_service.py`, `backend/app/services/memory_service.py`, `backend/app/models/chat.py`, `backend/app/models/conversation.py`, existing tests under `tests/`
   - What must be implemented: Map where system prompts, message history, memory context, file context, conversation metadata, and timestamps currently enter the Grok request. This step is a pure read-only audit — do NOT make any code changes or alter runtime behavior yet.
   - Success criteria: A short implementation note or inline TODOs identify which prompt-building responsibilities will move into `PromptService`, without changing runtime behavior yet.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `docs: audit prompt assembly for time-aware foundation`
   - Rough time estimate: 1-2 hours

2. **Create `TimeContextService`**
   - Exact files to create or modify: `backend/app/services/time_context_service.py`
   - What must be implemented: A service that returns current server time, timezone label, ISO timestamp, date, weekday, and human-readable clock context. Include helpers for calculating deltas from previous timestamps.
   - Success criteria: The service can produce stable, testable time context from an injectable `now` value and handles missing timestamps gracefully.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_time_context_service.py`
   - Suggested git commit message: `feat: add time context service`
   - Rough time estimate: 2-3 hours

3. **Add tests for time context and delta formatting**
   - Exact files to create or modify: `tests/test_time_context_service.py`
   - What must be implemented: Unit tests for current time output, timezone formatting, same-day deltas, multi-day deltas, week/month-scale deltas, future timestamp handling, and missing timestamp behavior.
   - Success criteria: Tests prove Rex can say practical things like “2 days ago,” “earlier today,” and “about 3 weeks ago” from stored timestamps.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_time_context_service.py`
   - Suggested git commit message: `test: cover time context delta formatting`
   - Rough time estimate: 2-3 hours

4. **Create `PromptService` skeleton**
   - Exact files to create or modify: `backend/app/services/prompt_service.py`, optionally `backend/app/dependencies.py`
   - What must be implemented: A dedicated service that accepts user message, recent messages, relevant memories, file context, conversation metadata, and time context, then returns Grok-ready message payloads.
   - Success criteria: Prompt assembly logic exists outside `ChatService`, has a narrow public API, and can be unit tested without calling Grok or Supabase.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add prompt service skeleton`
   - Rough time estimate: 2-4 hours

5. **Move Rex personality instructions into `PromptService`**
   - Exact files to create or modify: `backend/app/services/prompt_service.py`, `backend/app/services/ai_service.py`
   - What must be implemented: Define the founder-first Rex personality prompt in one place by copying the exact instructions from the latest `REX_VISION.md` (section 1): direct, honest, no fake positivity, practical accountability, sensitive personal context allowed, voice-friendly wording, and no generic filler.
   - Success criteria: `AIService` stays focused on Grok API transport while `PromptService` owns behavioral instructions and prompt composition.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `refactor: move rex personality into prompt service`
   - Rough time estimate: 2-3 hours

6. **Inject current time and session-gap context into every chat prompt**
   - Exact files to create or modify: `backend/app/services/prompt_service.py`, `backend/app/services/chat_service.py`, `backend/app/services/time_context_service.py`
   - What must be implemented: Include current server time, timezone, weekday, conversation timestamp metadata, and last-message delta in the prompt sent to Grok for both streaming and non-streaming chat.
   - Success criteria: Every Grok call receives explicit time context, and behavior remains compatible with existing JSON, multipart, and streaming chat paths.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: inject time context into chat prompts`
   - Rough time estimate: 3-5 hours

7. **Add memory-age annotations to retrieved long-term memories**
   - Exact files to create or modify: `backend/app/services/memory_service.py`, `backend/app/services/prompt_service.py`, `backend/app/services/time_context_service.py`, existing memory tests
   - What must be implemented: When relevant memories are inserted into the prompt, include practical age labels based on `created_at` or `updated_at`, such as “saved 12 days ago.”
   - Success criteria: Grok can distinguish recent events from older facts, and prompt memory sections remain under the existing budget/truncation limits.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: annotate retrieved memories with age`
   - Rough time estimate: 2-4 hours

8. **Refactor `ChatService` to delegate all prompt construction**
   - Exact files to create or modify: `backend/app/services/chat_service.py`, `backend/app/services/prompt_service.py`, related tests in `tests/`
   - What must be implemented: Remove direct prompt/message assembly from `ChatService` where practical and call `PromptService` for both standard responses and streaming responses.
   - Success criteria: `ChatService` orchestrates validation, persistence, retrieval, Grok calls, streaming, and memory extraction, but no longer owns prompt text rules.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `refactor: centralize chat prompt assembly`
   - Rough time estimate: 4-6 hours

9. **Add prompt-shape tests**
   - Exact files to create or modify: `tests/test_prompt_service.py`, update existing chat route/service tests if needed
   - What must be implemented: Tests that verify prompt output includes Rex personality, current time, session delta, conversation context, relevant memories with ages, and file context when present.
   - Success criteria: Tests fail if a future refactor accidentally removes time awareness or founder-specific personality instructions.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_prompt_service.py`
   - Suggested git commit message: `test: cover time-aware prompt assembly`
   - Rough time estimate: 3-4 hours

10. **Run full backend validation and manual time-gap test**
    - Exact files to create or modify: `docs/action_plans/action_plan_1.md` only if completion notes are added
    - What must be implemented: Run the full backend test suite, then manually simulate a conversation with an old previous message timestamp and confirm Rex receives enough context to acknowledge elapsed time.
    - Success criteria: Full backend tests pass, no existing streaming/non-streaming behavior regresses, and manual testing confirms time context is visible in the Grok prompt or response.
    - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
    - Suggested git commit message: `test: validate time-aware prompt foundation`
    - Rough time estimate: 1-2 hours

## Plan Completion Checklist
- [x] All 10 checklist items completed
- [x] All new/updated tests passing
- [x] `PYTHONPATH=backend python3 -m pytest -q tests` returns all tests passing
- [x] Manual test: send a message after a simulated time gap and verify time awareness appears in the response
- [x] Code style and type checks pass
- [x] Ready for Action Plan 2

## Revision History
- 2026-05-12 - Action Plan 1 created from Alignment Plan and updated REX_VISION.md
