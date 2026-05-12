```markdown
# FIX_PLAN.md

Date: 2026-05-11  
- Updated 2026-05-11: Added shared HTTP client, Riverpod setup, hardcoded URL fix, and clarified partial-history step.  
Version: 1.1  
Overall Goal: Move Rex from a 25% backend foundation/static Flutter shell into a reliable, production-ready Flutter + FastAPI + Grok + Supabase AI chat app with long-term memory.

## Executive Summary

Current status: **25% complete**.  
One-sentence insight: Rex has the right backend direction, but the app is not yet usable because the Flutter chat UI is still disconnected and the backend still has blocking I/O and incomplete API surfaces.

## Prioritized Phases

| Phase | Name | Depends On | Primary Outcome |
|---|---|---|---|
| 0 | Backend Stability & Reliability | None | Completed: backend is non-blocking, supports JSON chat, handles config/errors safely |
| 1 | Core Chat Connectivity | Phase 0 | Completed: Flutter sends messages and renders real responses |
| 2 | Conversation Management | Phase 1 | User can create, list, switch, and delete conversations |
| 3 | Memory System Completion | Phase 2 | Long-term memory is visible, editable, and more relevant |
| 4 | File Uploads, Polish, UX & Error States | Phase 1-3 | App feels reliable and usable for real users |
| 5 | Testing, Documentation & Production Readiness | All phases | Stable release path with coverage and deployment docs |

---

## Detailed Checklist

## Phase 0 - Backend Stability & Reliability - Completed

### 0.0 Create Reusable AsyncHTTPClient Service - Completed

- Why / dependencies: Both Grok and Supabase calls need the same async client with proper timeouts, limits, retries, and lifecycle management.
- Files to create or modify:
  - `backend/app/services/http_client.py`
  - `backend/app/main.py`
  - `backend/requirements.txt`
- Definition of Done:
  - Single shared `AsyncClient` instance exists.
  - Client is initialized with `@app.on_event("startup")`.
  - Client is closed with `@app.on_event("shutdown")`.
  - Client has explicit timeout and connection limit configuration.
  - Client is used by both `AIService` and `SupabaseMemoryService`.
- Pitfalls / edge cases:
  - Avoid creating a new HTTP client per request.
  - Do not leak open connections on shutdown.
  - Keep timeouts configurable enough for long Grok responses.
  - Be careful not to log secrets in request headers.
- Effort: Medium
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 0.1 Replace Blocking Grok HTTP Calls - Completed

- Why / dependencies: `AIService.generate_response()` currently uses blocking `urllib.request.urlopen()` inside an async route path. This can stall FastAPI under concurrent requests. Depends on `0.0`.
- Files to modify:
  - `backend/app/services/ai_service.py`
  - `backend/requirements.txt`
  - tests as needed
- Definition of Done:
  - Grok calls use the shared async HTTP client.
  - `generate_response()` becomes async.
  - Route and chat service await the AI call.
  - Existing backend tests pass.
- Pitfalls / edge cases:
  - Timeout handling must remain explicit.
  - HTTP status errors should map to controlled `AIServiceError`.
  - Keep Grok API key server-side only.
- Effort: Medium
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 0.2 Replace Blocking Supabase HTTP Calls - Completed

- Why / dependencies: `SupabaseMemoryService._request()` also uses blocking `urlopen()`, so every memory read/write blocks the event loop. Depends on `0.0`.
- Files to modify:
  - `backend/app/services/memory_service.py`
  - `backend/requirements.txt`
  - `backend/app/services/chat_service.py`
  - tests as needed
- Definition of Done:
  - Supabase requests use the shared async HTTP client.
  - Memory service methods that hit Supabase are async.
  - Chat service awaits memory operations.
  - All tests pass.
- Pitfalls / edge cases:
  - Multiple memory calls in one chat request can become slow; consider parallelizing safe reads later.
  - Preserve Supabase headers: `apikey`, `Authorization`, `Prefer`.
  - Keep service-role key out of Flutter.
- Effort: Large
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 0.3 Add JSON Support for `/chat` - Completed

- Why / dependencies: `/chat` currently only supports `multipart/form-data`. Normal app messages should be JSON. Depends on `0.1` and `0.2`.
- Files to modify:
  - `backend/app/routes/chat.py`
  - `backend/app/models/chat.py`
  - tests for route behavior
- Definition of Done:
  - Plain JSON requests are accepted for normal text chat.
  - Multipart remains available for file upload.
  - JSON body supports `message` and optional `conversation_id`.
  - Empty messages still return `400`.
- Pitfalls / edge cases:
  - FastAPI cannot cleanly mix JSON body and file upload in one handler; use separate endpoints or content-type branching carefully.
  - Avoid breaking existing multipart file flow.
- Effort: Medium
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 0.4 Tighten Backend Config Validation - Completed

- Why / dependencies: `grok_model` defaults to `None`, causing runtime `503` until env is configured.
- Files to modify:
  - `backend/app/config.py`
  - `backend/.env.example`
  - `README.md`
- Definition of Done:
  - Missing `GROK_API_KEY`, `GROK_MODEL`, `SUPABASE_URL`, or `SUPABASE_SERVICE_ROLE_KEY` produces a clear startup or request-time error.
  - `.env.example` documents all required values.
  - No local model references exist.
- Pitfalls / edge cases:
  - Startup failure is clearer for production, but request-time failure can be easier during local development.
  - Do not log secrets.
- Effort: Small
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 0.5 Normalize Backend Error Response Contract - Completed

- Why / dependencies: The frontend will need consistent error handling. Current backend errors come from multiple services and may not share a stable response shape.
- Files to create or modify:
  - `backend/app/routes/chat.py`
  - `backend/app/models/chat.py`
  - possible new `backend/app/models/errors.py`
- Definition of Done:
  - Backend returns predictable error JSON for validation, AI, memory, and file errors.
  - Error responses include a user-safe message.
  - Internal exception details are not leaked.
  - Tests cover at least one AI error, memory error, validation error, and file error.
- Pitfalls / edge cases:
  - Do not expose Grok or Supabase raw error payloads to the client.
  - Preserve useful status codes: `400`, `404`, `413`, `500`, `503`.
- Effort: Medium
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 0.6 Improve Partial Conversation History on Failures (Phase 1 improvement) - Completed

- Why / dependencies: User message and long-term memory are saved before Grok succeeds. If Grok fails, the transcript may contain a user message with no assistant reply and memory extracted from a failed turn. Start with simple post-success persistence; full transactional solution may be deferred to a later phase.
- Files to modify:
  - `backend/app/services/chat_service.py`
  - `backend/app/services/memory_service.py`
  - possible schema change in `backend/supabase_schema.sql`
- Definition of Done:
  - File validation still happens before persistence.
  - Grok failures do not create misleading assistant messages.
  - Simple implementation saves user/assistant transcript and long-term memory only after Grok succeeds.
  - Full Supabase transactional/RPC solution is documented if deferred.
- Pitfalls / edge cases:
  - Supabase REST does not provide easy multi-table transactions without RPC.
  - Post-success persistence means a successful Grok answer could still fail to save; handle and report that clearly.
  - Consider adding `status` fields or a Supabase RPC for atomic chat-turn writes later.
- Effort: Large
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

---

## Phase 1 - Core Chat Connectivity

### 1.0 Set Up State Management (Riverpod) - Completed

- Why / dependencies: `ChatPage` cannot scale with conversation tracking, messages list, loading states without proper state management.
- Files to create or modify:
  - `pubspec.yaml`
  - `lib/main.dart`
  - create `lib/core/providers.dart` or similar
  - create chat provider/state files as needed
- Definition of Done:
  - Riverpod is added to the Flutter project.
  - App is wrapped in `ProviderScope`.
  - A `ChatProvider` exists for messages, loading, and `conversationId`.
  - Existing widget test still passes.
- Pitfalls / edge cases:
  - Keep provider structure simple at first.
  - Avoid over-abstracting before conversation management exists.
  - Make API dependency mockable for tests.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 1.1 Replace `ChatApi.sendMessage()` Return Type - Completed

- Why / dependencies: `ChatApi.sendMessage()` currently returns only a `String`, losing `conversation_id` and message history. Also fix hardcoded `baseUrl` in `ChatApi.dart` by using environment configuration / dotenv.
- Files to modify:
  - `lib/services/chat_api.dart`
  - create `lib/features/chat/data/chat_models.dart`
  - `pubspec.yaml` if dotenv/config package is needed
  - possible `lib/core/config/app_config.dart`
- Definition of Done:
  - API returns a typed response model with `conversationId`, `response`, and `messages`.
  - Backend errors are parsed into user-safe messages.
  - Hardcoded `http://209.126.87.50:8000` is removed.
  - Backend base URL comes from environment configuration or dotenv.
  - Hardcoded response shape assumptions are removed.
- Pitfalls / edge cases:
  - Backend may return validation errors as JSON with `detail`.
  - Network errors should not crash the UI.
  - Mobile builds need a reliable way to inject dev/prod backend URLs.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 1.2 Wire `ChatPage._onSendTapped()` to Backend - Completed

- Why / dependencies: The send button currently only clears the input.
- Files to modify:
  - `lib/features/chat/presentation/pages/chat_page.dart`
  - `lib/services/chat_api.dart`
  - Riverpod chat provider/state files
- Definition of Done:
  - Tapping send appends a user message locally.
  - Flutter calls backend.
  - Assistant response renders in the chat.
  - Input clears only after the message is accepted into UI state.
- Pitfalls / edge cases:
  - Prevent double-send while request is in flight.
  - Preserve typed text if request setup fails before local append.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 1.3 Add Conversation ID Tracking in Flutter - Completed

- Why / dependencies: Backend returns `conversation_id`, but Flutter currently does not store or reuse it.
- Files to modify:
  - `lib/features/chat/presentation/pages/chat_page.dart`
  - `lib/features/chat/data/chat_models.dart`
  - Riverpod chat provider/state files
- Definition of Done:
  - First message creates a conversation.
  - Returned `conversation_id` is stored.
  - Follow-up messages send the same `conversation_id`.
- Pitfalls / edge cases:
  - Reset conversation ID when user starts a new chat.
  - Handle backend `404 Conversation not found`.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 1.4 Render Dynamic Messages - Completed

- Why / dependencies: Current chat page renders one static welcome bubble.
- Files to modify:
  - `lib/features/chat/presentation/pages/chat_page.dart`
  - `lib/features/chat/presentation/widgets/chat_message_bubble.dart`
  - `lib/features/chat/domain/chat_message.dart`
- Definition of Done:
  - User and assistant messages render from state.
  - Bubble alignment uses role.
  - Static welcome state only appears when there are no real messages.
- Pitfalls / edge cases:
  - Long messages should wrap cleanly.
  - Auto-scroll to latest message after send/receive.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 1.5 Add Basic Loading and Error States - Completed

- Why / dependencies: The app currently gives no feedback during requests or failures.
- Files to modify:
  - `lib/features/chat/presentation/pages/chat_page.dart`
  - optional `typing_indicator.dart`
  - Riverpod chat provider/state files
- Definition of Done:
  - Send button disabled while sending.
  - Typing/loading indicator appears while waiting.
  - Backend/network errors show a visible retry-friendly message.
- Pitfalls / edge cases:
  - Do not duplicate user messages on retry.
  - Make sure loading state clears on exceptions.
- Effort: Small
- Suggested testing command:
  - `flutter test`

---

## Phase 2 - Conversation Management

### 2.1 Add Backend Conversation Routes - Completed

- Why / dependencies: There is no route to list, create, switch, or delete conversations.
- Files to create or modify:
  - `backend/app/routes/conversations.py`
  - `backend/app/services/memory_service.py`
  - `backend/app/main.py`
  - `backend/app/models/chat.py` or new `backend/app/models/conversation.py`
- Definition of Done:
  - `GET /conversations`
  - `POST /conversations`
  - `GET /conversations/{id}/messages`
  - `DELETE /conversations/{id}`
  - Tests cover basic behavior.
- Pitfalls / edge cases:
  - Deleting a conversation should cascade messages.
  - Decide whether long-term memories sourced from deleted conversations remain active.
- Effort: Large
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 2.2 Add Flutter Conversation Models and API - Completed

- Why / dependencies: Flutter needs typed APIs for conversation list and thread loading.
- Files to create:
  - `lib/features/chat/data/conversation_api.dart`
  - `lib/features/chat/data/chat_models.dart`
  - `lib/features/chat/domain/conversation.dart`
- Definition of Done:
  - Flutter can fetch conversations.
  - Flutter can fetch messages for a conversation.
  - Flutter can request conversation deletion.
- Pitfalls / edge cases:
  - Empty conversation list state.
  - Deleted active conversation should reset the chat view.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 2.3 Build Conversation List / Switch UI - Completed

- Why / dependencies: Production chat needs thread management.
- Files to modify or create:
  - `lib/features/chat/presentation/pages/conversation_list_page.dart`
  - `lib/features/chat/presentation/pages/chat_page.dart`
  - Riverpod conversation provider/state files
- Definition of Done:
  - User can open previous conversations.
  - Active conversation messages load into chat.
  - User can start a new conversation.
- Pitfalls / edge cases:
  - Avoid losing unsent draft text accidentally.
  - Handle loading old messages gracefully.
- Effort: Large
- Suggested testing command:
  - `flutter test`

### 2.4 Add Delete Conversation UX - Completed

- Why / dependencies: User needs control over stored conversations.
- Files to modify:
  - conversation routes and Flutter conversation UI
- Definition of Done:
  - Delete action requires confirmation.
  - Deleted conversation disappears from list.
  - Active deleted conversation returns to empty chat.
- Pitfalls / edge cases:
  - Backend failure after optimistic UI delete.
  - Supabase cascade behavior should be verified.
- Effort: Medium
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests && flutter test`

---

## Phase 3 - Memory System Completion

### 3.1 Add Backend Memory Routes - Completed

- Why / dependencies: Backend has memory service methods but no user-facing memory API.
- Files to create or modify:
  - `backend/app/routes/memory.py`
  - `backend/app/models/memory.py`
  - `backend/app/services/memory_service.py`
  - `backend/app/main.py`
- Definition of Done:
  - `GET /memory`
  - `PATCH /memory/{id}`
  - `DELETE` or deactivate `/memory/{id}`
  - Filter by memory type and active status.
- Pitfalls / edge cases:
  - Prefer soft delete/deactivate over hard delete initially.
  - Validate `memory_type`.
- Effort: Medium
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 3.2 Build Flutter Memory Screen - Completed

- Why / dependencies: Memory must be visible and editable for trust.
- Files to create or modify:
  - `lib/features/memory/data/memory_api.dart`
  - `lib/features/memory/data/memory_models.dart`
  - `lib/features/memory/presentation/pages/memory_page.dart`
  - remove or replace `lib/features/memory/memory_placeholder.dart`
- Definition of Done:
  - User can view remembered facts, preferences, and events.
  - User can edit memory content.
  - User can deactivate/delete wrong memories.
- Pitfalls / edge cases:
  - Sensitive memories need clear controls.
  - Empty memory state should be clear and non-scary.
- Effort: Large
- Suggested testing command:
  - `flutter test`

### 3.3 Improve Long-Term Memory Retrieval - Completed

- Why / dependencies: Current retrieval is global by importance/recency, not query-relevant.
- Files to modify:
  - `backend/app/services/memory_service.py`
  - possibly `backend/supabase_schema.sql`
- Definition of Done:
  - Retrieval considers current message/query.
  - Context injection includes only relevant memories.
  - Memory prompt stays within context budget.
- Pitfalls / edge cases:
  - Keyword-only retrieval may miss meaning.
  - Too much memory can degrade answers.
- Effort: Large
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 3.4 Add Grok-Powered Memory Extraction - Completed

- Why / dependencies: Current extraction is regex/rule-based and will miss important life context.
- Files to modify:
  - `backend/app/services/memory_service.py`
  - `backend/app/services/ai_service.py`
  - possibly new `backend/app/services/memory_extraction_service.py`
- Definition of Done:
  - After successful chat turn, backend asks Grok or a structured extraction prompt for memory candidates.
  - Candidates include type, content, importance, and rationale.
  - Duplicate memories are avoided or merged.
- Pitfalls / edge cases:
  - Do not save every emotional sentence as permanent memory.
  - Avoid extracting sensitive memories without user control.
- Effort: Large
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

---

## Phase 4 - File Uploads, Polish, UX & Error States

### 4.1 Add Flutter File Picker and Upload Flow - Completed

- Why / dependencies: Backend supports file uploads, but Flutter has no upload UI.
- Files to modify or create:
  - `pubspec.yaml`
  - `lib/features/chat/presentation/widgets/chat_input_bar.dart`
  - `lib/features/chat/presentation/pages/chat_page.dart`
  - `lib/services/chat_api.dart`
- Definition of Done:
  - User can attach `.txt`, `.md`, or `.csv`.
  - Selected file is shown before send.
  - File is sent as multipart with message.
- Pitfalls / edge cases:
  - Mobile file permissions.
  - File size should be checked before upload when possible.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 4.2 Add File Validation Feedback in Flutter - Completed

- Why / dependencies: Backend validates files, but app should explain failures clearly.
- Files to modify:
  - Flutter chat page/input widgets
  - `ChatApi` error handling
- Definition of Done:
  - Unsupported file type shows user-friendly error.
  - Oversized file shows 2MB max message.
  - UTF-8 validation failure displays clearly.
- Pitfalls / edge cases:
  - Backend error format may vary.
  - Avoid raw exception dumps in UI.
- Effort: Small
- Suggested testing command:
  - `flutter test`

### 4.3 Improve Visual Chat Polish - Completed

- Why / dependencies: The shell is clean but not production-level chat UX.
- Files to modify:
  - chat page
  - message bubble
  - app theme
- Definition of Done:
  - Responsive layout works on small phones.
  - Typing/loading state looks intentional.
  - Error states are visible but not disruptive.
  - Empty state transitions cleanly into real chat.
- Pitfalls / edge cases:
  - Long text overflow.
  - Keyboard/safe area issues.
  - Scroll position bugs.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 4.4 Add Optional Streaming Response Support - Completed

- Why / dependencies: Vision includes real-time messaging ideally with streaming.
- Files to modify:
  - `backend/app/services/ai_service.py`
  - `backend/app/routes/chat.py`
  - Flutter API layer and chat UI
- Definition of Done:
  - Backend can stream Grok output.
  - Flutter progressively renders assistant response.
  - Non-streaming fallback remains available.
- Pitfalls / edge cases:
  - Streaming over mobile networks can fail mid-response.
  - Need cancellation behavior.
- Effort: Large
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests && flutter test`

---

## Phase 5 - Testing, Documentation & Production Readiness

### 5.1 Add FastAPI Route Tests - Completed

- Why / dependencies: Current tests focus on services with fakes, not route behavior.
- Files to create or modify:
  - `tests/test_chat_routes.py`
  - `tests/test_memory_routes.py`
  - `tests/test_conversation_routes.py`
- Definition of Done:
  - Tests cover JSON chat, multipart chat, validation, and error paths.
  - Tests do not require real Grok or Supabase.
- Pitfalls / edge cases:
  - Dependency injection should allow test doubles.
  - Avoid hitting live external services in CI.
- Effort: Medium
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests`

### 5.2 Add Flutter Widget Tests for Real Chat States - Completed

- Why / dependencies: Current Flutter test only checks the shell exists.
- Files to modify:
  - `test/widget_test.dart`
  - additional feature tests
- Definition of Done:
  - Tests cover empty state, sending state, assistant response, and error state.
  - Tests cover conversation switching if implemented.
- Pitfalls / edge cases:
  - Mock API layer cleanly.
  - Avoid brittle visual assertions.
- Effort: Medium
- Suggested testing command:
  - `flutter test`

### 5.3 Add Environment and Run Documentation - Completed

- Why / dependencies: The app needs clear setup for Grok, Supabase, backend, and Flutter.
- Files to modify:
  - `README.md`
  - `REX_VISION.md`
  - `.env.example`
- Definition of Done:
  - New developer can run backend tests.
  - New developer can run Flutter app.
  - Required Supabase SQL setup is documented.
  - Required env vars are documented.
- Pitfalls / edge cases:
  - Keep docs in sync with actual env var names.
  - Do not include real secrets.
- Effort: Small
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests && flutter test`

### 5.4 Prepare Deployment Path - Completed

- Why / dependencies: Production readiness requires stable deployment and environment handling.
- Files to create or modify:
  - backend deployment docs/config
  - VPS `systemd` deployment guidance
  - CI workflow later
- Definition of Done:
  - Backend can be deployed with env vars.
  - Flutter can point to dev/prod backend via config.
  - Secrets are not committed.
- Pitfalls / edge cases:
  - CORS setup for mobile/dev clients.
  - HTTPS required for production mobile reliability.
- Effort: Large
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests && flutter test`

### 5.5 Docker Cleanup - Completed

- Why / dependencies: The initial deployment path is a single VPS with Python virtualenv, `systemd`, and Nginx/Caddy. Keeping an optional Docker path adds confusion without solving a current deployment problem.
- Files modified:
  - Removed `backend/Dockerfile`
  - Removed `.dockerignore`
  - Updated `docs/deployment.md`
  - Updated `REX_VISION.md`
- Definition of Done:
  - Deployment docs recommend one clear VPS path.
  - No Dockerfile remains in the project.
  - Docker references are removed from active docs.
- Effort: Small
- Suggested testing command:
  - `PYTHONPATH=backend python3 -m pytest -q tests && flutter test`

---

## Appendix

## Remaining Technical Debt

- Flutter chat is still static and disconnected.
- `ChatApi.baseUrl` is hardcoded to a raw IP.
- `ChatApi` discards `conversation_id` and message history.
- Backend uses blocking HTTP in async routes.
- `/chat` lacks JSON support.
- Supabase service logic is concentrated in one service instead of repositories/client abstraction.
- Memory retrieval is not semantic or query-relevant.
- Long-term memory extraction is simple regex/rules.
- `last_accessed_at` is not updated on retrieval.
- No backend memory routes.
- No Flutter memory UI.
- No conversation management routes or screens.
- No streaming.
- No route-level backend tests.
- No integration test path for real Grok/Supabase.
- Working tree contains large unstaged migration changes and should be cleaned up before major new work.

## Key Risks

- Blocking I/O can make the backend feel frozen under multiple users or long Grok calls.
- Partial writes can create confusing conversation history after failures.
- Poor memory extraction can store inaccurate or overly sensitive information.
- No memory UI means the user cannot correct Rex.
- Hardcoded backend URL makes mobile deployment brittle.
- Lack of JSON endpoint makes normal app chat more awkward than necessary.

## Nice-to-Haves

- Streaming Grok responses.
- Voice input and assistant playback.
- Push-to-talk mode.
- Background/lock-screen-friendly voice behavior where mobile platforms allow.
- Semantic memory search with embeddings.
- Topic summaries for work, relationships, money, immigration, goals, and daily life.
- Local draft persistence.
- Conversation search.
- Memory confidence scores.
- Memory deduplication and merge flow.

## Testing Strategy

- Backend unit tests:
  - AI service error handling.
  - Supabase memory service request/response handling.
  - Chat service orchestration.
  - Memory extraction logic.

- Backend route tests:
  - JSON `/chat`.
  - Multipart `/chat`.
  - Conversation routes.
  - Memory routes.
  - Error responses.

- Flutter tests:
  - Empty chat state.
  - Send message flow.
  - Loading indicator.
  - Error state.
  - Conversation switching.
  - Memory list/edit/delete UI.
  - File picker states using mocks.

- Manual smoke tests:
  - Start backend with real env.
  - Send first message from Flutter.
  - Continue same conversation.
  - Confirm Supabase rows are created.
  - Confirm long-term memory appears and can be edited.
  - Test Grok outage/error behavior.
  - Test file upload success and rejection paths.

## Execution Rule

Work one step at a time. Complete the backend stability phase before major frontend work. Each step should end with passing tests and a short status update before moving to the next step.
```
