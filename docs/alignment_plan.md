# REX Alignment Plan

## 1. Executive Summary

Rex is roughly **4/10 aligned** with the updated founder vision overall, and closer to **2/10 aligned** with the new voice-first daily-driver requirement specifically. The strongest foundation is already in place: Flutter chat UI, FastAPI backend, Grok API integration, streaming responses, Supabase-backed conversations/messages/long-term memory, memory UI, file upload support, tests, and VPS deployment docs. The biggest risks are that the updated vision now depends on capabilities that do not exist yet: voice-first interaction, locked-screen/pocket workflow, current-time injection, time-delta reasoning, entity tracking, durable personal rules, plan tracking, and accountability logic. The project is no longer blocked by basic chat plumbing; it is now blocked by missing memory intelligence and missing voice infrastructure.

## 2. Vision vs Reality Matrix

| Vision Section / Requirement | Current Implementation Status (Fully Done / Partially Done / Not Started / Needs Refactor) | Key Files / Code Involved | Gap Description & Technical Reason | Effort Estimate (Small / Medium / Large / Unknown) | Priority (P0 / P1 / P2) |
|---|---|---|---|---|---|
| Founder-first personal daily driver | Partially Done | `REX_VISION.md`, `README.md`, `docs/deployment.md` | Project direction and docs now say founder-first, but product behavior still mostly behaves like a generic chat app with memory. No founder-specific rules, plans, entities, or accountability layer exists. | Medium | P0 |
| Voice-first primary interface | Not Started | No `lib/features/voice/` implementation exists | Flutter app is text-first. There is no STT, TTS, recorder UI, audio state machine, voice service, voice permissions, or voice route. | Large | P0 |
| Pocket / locked-screen / background voice workflow | Not Started | No background audio, native platform config, or voice service files | This requires platform-specific iOS/Android capability decisions, background audio mode, permissions, and realistic OS-limit handling. Current Flutter app only works as foreground text chat. | Large / Unknown | P0 |
| Flutter speech-to-text pipeline | Not Started | No STT dependencies in `pubspec.yaml`; no `speech_to_text_service.dart` | No speech recognition package, permission flow, transcript state, partial transcript UI, or on-device/offline mode strategy exists. | Medium | P0 |
| Flutter text-to-speech playback | Not Started | No TTS dependency/service | Grok responses are streamed as text only. No TTS queue, interruption handling, playback state, audio route, or speaker/headphones behavior exists. | Medium | P0 |
| Streaming text chat | Fully Done | `lib/services/chat_api.dart`, `lib/features/chat/application/chat_controller.dart`, `backend/app/routes/chat.py`, `backend/app/services/ai_service.py`, `backend/app/services/chat_service.py` | SSE streaming exists and Flutter progressively renders assistant tokens. This is a strong base for TTS, but TTS does not consume the stream yet. | Small for polish | P0 |
| Text chat fallback | Fully Done | `lib/features/chat/presentation/pages/chat_page.dart`, `lib/features/chat/presentation/widgets/chat_input_bar.dart`, `lib/services/chat_api.dart` | Text chat is functional, supports loading/error states, streaming, conversations, and file attachments. | Small | P1 |
| Conversation management | Fully Done | `backend/app/routes/conversations.py`, `lib/features/chat/presentation/pages/conversation_list_page.dart`, `lib/features/chat/application/conversation_controller.dart` | List/create/switch/delete are implemented with tests. Needs future UX polish but meets current requirement. | Small | P1 |
| Long-term memory across months | Partially Done | `backend/supabase_schema.sql`, `backend/app/services/memory_service.py`, `backend/app/services/memory_extraction_service.py`, `lib/features/memory/` | `long_term_memory` stores durable memories with timestamps and active flag. Retrieval is basic keyword/concept scoring, not true month-scale semantic memory with summaries, plans, or entities. | Large | P0 |
| Memory UI for review/edit/deactivate | Partially Done | `lib/features/memory/presentation/pages/memory_page.dart`, `backend/app/routes/memory.py` | User can list/edit/deactivate facts/preferences/events. No search, grouping, entity view, plan view, personal rules view, or “why recalled” UI. | Medium | P1 |
| Grok-powered memory extraction | Partially Done | `backend/app/services/memory_extraction_service.py` | Extraction exists for `fact`, `preference`, `event`. Prompt does not yet extract entities, rules, plans, deadlines, commitments, or relationship-specific context into structured tables. | Medium | P0 |
| Query-aware memory retrieval | Partially Done | `backend/app/services/memory_service.py` | Keyword + concept overlap + importance + recency exists. No embeddings, vector search, entity joins, plan retrieval, personal-rule boosting, or time-delta-aware scoring. | Large | P0 |
| Time awareness: current server time in every prompt | Not Started | `backend/app/services/chat_service.py`, missing `time_context_service.py`, missing `prompt_service.py` | `chat_service` sends conversation history and memory to Grok but does not inject current server time, timezone, day of week, or clock context. | Medium | P0 |
| Time deltas since messages/events/commitments | Not Started | `backend/app/services/chat_service.py`, `backend/app/services/memory_service.py`, missing `time_context_service.py` | Timestamps exist in Supabase, but no code calculates “2 days ago”, “31 days since budget commitment”, deadline deltas, or session gaps for prompt injection. | Medium | P0 |
| Prompt assembly as explicit service | Not Started | Missing `backend/app/services/prompt_service.py` | Prompt construction is embedded in `ChatService` and `AIService.system_prompt`. This will not scale to time, entities, personal rules, plans, voice metadata, and file context. Needs extraction into a dedicated service. | Medium | P0 |
| Entity tracking: people like Clara/Melissa, jobs, plans | Not Started | Missing `entity_service.py`, `entity_repository.py`, Supabase entity tables | Current memory is unstructured text with `fact/preference/event`. No entity table, alias handling, relationship context, timeline per person, or retrieval by entity mention exists. | Large | P0 |
| Personal rules: no Uber, Bom Dough only, budget caps | Not Started | Missing personal rules schema/service/UI | Rules may be saved as generic memories if Grok extracts them, but there is no durable rule type, enforcement/retrieval priority, violation detection, or accountability logic. | Large | P0 |
| Accountability and pattern recognition | Not Started | Missing accountability service, plan/rule models, finance pattern logic | Rex cannot detect “you promised this last month” except if a generic memory happens to be retrieved. Needs commitments, rules, event timelines, and behavior comparisons. | Large | P0 |
| Multi-month plans and progress tracking | Not Started | Missing plan schema/service/UI | No plan table, milestones, target dates, progress state, deadline deltas, or periodic review logic. Current `long_term_memory` cannot reliably maintain active plans. | Large | P0 |
| Uncensored / human-like / Grok-level personality | Partially Done | `backend/app/services/ai_service.py` | System prompt is direct and concise, but not founder-specific enough. It does not explicitly encode no-BS accountability, sensitive life topics, voice style, personal rules, or truth-seeking behavior. | Small / Medium | P0 |
| Sensitive real-life advice topics | Partially Done | `backend/app/services/ai_service.py`, `backend/app/services/memory_extraction_service.py` | Current prompt allows practical direct advice, and memory extraction mentions legal/financial/relationship context. But no specific founder domains are modeled: dating context, immigration strategy, money patterns, or personal constraints. | Medium | P0 |
| Supabase schema for conversations/messages/memory | Fully Done | `backend/supabase_schema.sql` | Core chat and generic memory schema exists and is usable. | Small | P1 |
| Supabase schema for entities/rules/plans | Not Started | `backend/supabase_schema.sql` | No `entities`, `entity_events`, `personal_rules`, `plans`, `plan_milestones`, or `commitments` tables exist. | Medium / Large | P0 |
| Voice metadata storage | Not Started | `backend/supabase_schema.sql`, no voice models | Schema does not store transcript source, audio duration, audio session, device state, or TTS playback metadata. | Medium | P1 |
| CSV/file upload, including Clarity finance CSV | Partially Done | `backend/app/services/file_service.py`, `lib/features/chat/domain/chat_attachment.dart`, `lib/features/chat/presentation/pages/chat_page.dart` | `.csv` upload is supported as text context. No Clarity-specific parser, finance insight service, recurring merchant detection, or budget review pipeline. | Medium | P1 |
| Space awareness later | Not Started | No code | Correctly future-only. No action needed for MVP. | Unknown | P2 |
| Privacy: secrets not in app | Fully Done | `lib/core/config/app_config.dart`, `backend/app/config.py`, `.gitignore`, docs | Flutter uses backend URL only. Grok/Supabase service keys stay backend-side. `.env` is ignored. | Small | P0 |
| Deployment readiness | Partially Done | `docs/deployment.md`, `backend/app/main.py`, `backend/app/config.py`, `README.md` | VPS deployment docs, lifespan handler, CORS, and env handling exist. Still missing actual systemd file, production logging, monitoring, health checks beyond `/`, and CI. | Medium | P1 |
| Test coverage | Partially Done | `tests/`, `test/` | Good service/route/widget coverage: backend 44 tests, Flutter 38 tests. No real Grok/Supabase integration test mode, voice tests, time-context tests, entity tests, or plan/rule tests. | Medium | P1 |
| Backend async reliability | Fully Done | `backend/app/services/http_client.py`, `backend/app/services/ai_service.py`, `backend/app/services/memory_service.py` | Grok and Supabase use async `httpx`. Shared HTTP lifecycle exists. | Small | P1 |
| Mobile UX polish for current chat | Partially Done | `lib/features/chat/presentation/pages/chat_page.dart`, `lib/features/chat/presentation/widgets/chat_message_bubble.dart` | Current text chat is polished enough for continued development. It is not voice-first and has no pocket mode. | Medium | P1 |

## 3. What’s Already Strong / Done Well

- The core stack is correct: Flutter, FastAPI, Grok API, Supabase, no Ollama, no SQLite.
- FastAPI now uses async Grok and Supabase calls through a shared HTTP client.
- `/chat` supports JSON, multipart uploads, and SSE streaming.
- Flutter chat is wired to the backend, renders dynamic user/assistant messages, supports streaming, and handles loading/errors.
- Conversation management exists end to end: list, create, switch, delete, and message retrieval.
- Supabase schema exists for `conversations`, `messages`, and `long_term_memory`.
- Grok-powered memory extraction exists and saves useful `fact/preference/event` memories after successful chat turns.
- Memory UI exists for listing, filtering, editing, and deactivating memories.
- File upload support exists for `.txt`, `.md`, and `.csv`.
- Deployment path is clean for VPS: virtualenv, `systemd`, Nginx/Caddy, env vars, CORS, and HTTPS guidance.
- Test coverage is strong for the current scope: backend route/service tests and Flutter API/controller/widget tests are in place.

## 4. Critical Gaps & Why They Exist

The largest gap is that Rex is still a text-first chat application, while the updated vision is voice-first. There is no `lib/features/voice/` implementation, no STT/TTS dependency, no recorder state machine, no platform permissions, no audio session handling, and no background/locked-screen strategy. This is a product-level blocker because the founder’s target workflow is walking with the phone in a pocket, not typing into a chat box.

The second critical gap is time awareness. The backend stores timestamps, but it does not inject current server time, user timezone, session gaps, event ages, or deadline deltas into prompts. This means Rex can still accidentally treat old context like it is current. `ChatService` directly assembles messages and memory context, and there is no `prompt_service.py` or `time_context_service.py` to enforce time context as a required prompt invariant.

The third critical gap is the lack of structured entity, rule, and plan storage. `long_term_memory` can hold generic facts, preferences, and events, but the updated vision requires Rex to remember specific people, recurring relationship context, personal rules, commitments, deadlines, and multi-month plans. Those need first-class schema and services, not just text memories. Without this, accountability will be unreliable and retrieval will be too dependent on keyword overlap.

The fourth critical gap is accountability logic. Rex currently retrieves memories and sends them to Grok, but it does not detect rule violations, compare current behavior to past commitments, run budget pattern checks, or surface missed plan milestones. The project needs explicit `personal_rules`, `commitments`, and `plans` models plus retrieval/violation logic before Rex can say, accurately, “you said you would stop doing this last month.”

The fifth gap is personality specialization. `AIService.system_prompt` is direct and low-fluff, which is good, but it is generic. It does not yet encode the founder-specific Rex personality from the updated vision: truth-seeking, no-BS, real-life sensitive topics, budget accountability, dating context, immigration stress, and voice-friendly conversational style. This should move into a prompt service so personality, time, memory, entities, rules, and plans are assembled consistently.

The sixth gap is finance intelligence. CSV upload exists, including `.csv`, but it is treated as raw file context. There is no Clarity parser, merchant/category extraction, recurring-spend detection, budget cap comparison, or monthly review logic. This is not required before the voice MVP, but it is central to the accountability vision.

The final gap is production hardening beyond “deployable.” The VPS path is documented and the backend is technically deployable, but there is no committed `systemd` unit template file, no CI, no structured logs, no real integration test mode, no monitoring, and no rate limiting. This is acceptable for founder dogfooding but should be addressed before broader use.

## 5. Recommended New Phase Structure

### Phase 6 - Time-Aware Prompt Foundation

- Goal: Make every Rex response aware of current time, session gaps, memory ages, and the founder-specific direct personality.
- Key deliverables:
  - `backend/app/services/time_context_service.py`
  - `backend/app/services/prompt_service.py`
  - Refactor `chat_service.py` so prompt assembly is centralized.
  - Inject server time, timezone, last-message delta, memory ages, and current conversation metadata into every Grok call.
  - Strengthen Rex personality prompt for founder-first directness and accountability.
  - Add backend tests for time-context injection and prompt shape.
- Estimated time (solo founder pace): 2-4 focused days.
- Dependencies: Existing chat service, message timestamps, memory retrieval.

### Phase 7 - Minimal Voice-First Personal Rex

- Goal: Make Rex usable as a voice-first personal assistant in foreground mode first.
- Key deliverables:
  - Add Flutter STT dependency and permission flow.
  - Add Flutter TTS dependency and playback service.
  - Create `lib/features/voice/` with `voice_service.dart`, `speech_to_text_service.dart`, `text_to_speech_service.dart`, and `voice_recorder_sheet.dart`.
  - Add push-to-talk button and voice state UI: idle, listening, transcribing, thinking, speaking, failed.
  - Send transcript through existing `/chat` streaming pipeline.
  - Speak streamed/final assistant response.
  - Add widget/controller tests for voice state transitions where practical.
- Estimated time (solo founder pace): 4-7 days for a usable foreground MVP.
- Dependencies: Phase 6 strongly recommended first so voice uses the correct prompt intelligence.

### Phase 8 - Entity, Rule, and Plan Memory Schema

- Goal: Move beyond generic long-term memory into structured founder life memory.
- Key deliverables:
  - Extend Supabase schema with `entities`, `entity_events`, `personal_rules`, `plans`, `plan_milestones`, and possibly `commitments`.
  - Add backend models/routes/services/repositories for these records.
  - Update memory extraction prompt to emit entity/rule/plan candidates.
  - Add retrieval that detects names like Clara/Melissa and pulls entity timeline context.
  - Add tests for extraction, deduplication, and retrieval.
- Estimated time (solo founder pace): 5-10 days.
- Dependencies: Phase 6 prompt service; existing Supabase memory service.

### Phase 9 - Accountability and Pattern Recognition

- Goal: Make Rex actively compare current behavior against past rules, commitments, and plans.
- Key deliverables:
  - Rule violation detection for money/transport/food delivery/coffee/rent categories.
  - Commitment tracking and missed-commitment retrieval.
  - Plan progress prompts and weekly/monthly review logic.
  - “Why Rex is bringing this up” metadata.
  - Flutter UI sections for rules, commitments, and plans.
- Estimated time (solo founder pace): 1-2 weeks.
- Dependencies: Phase 8 structured memory.

### Phase 10 - Background & Locked-Screen Voice Continuation

- **Goal**: Enable voice conversations to continue naturally when the user minimizes the app, switches to other apps, or locks/turns off the screen — similar to how Grok or ChatGPT voice mode behaves.
- **Key deliverables**:
  - Research and implement feasible background audio handling on iOS and Android within platform limits.
  - Configure proper audio session categories and background modes.
  - Handle interruptions (incoming calls, notifications, headphones, screen lock).
  - Ensure the voice flow (listening → thinking → speaking) survives app backgrounding and screen off where possible.
  - Add clear UX feedback when background continuation is limited by the OS.
  - Document realistic platform constraints.
- **Estimated time (solo founder pace)**: 1-3 weeks depending on platform constraints.
- **Dependencies**: Phase 7 voice MVP.

### Phase 11 - General File Upload & Contextual Memory

- **Goal**: Allow the user to upload various simple files (budget CSVs, .txt files with rhymes, notes, documents, etc.) and have them added to the current conversation context or stored as long-term memory.
- **Key deliverables**:
  - Improve and generalize the existing file upload flow.
  - Support common file types and make upload part of natural conversation flow.
  - Allow the user to say things like “I just uploaded my new budget” or “I uploaded a .txt with some rhymes I did” and have Rex understand and reference the content.
  - Basic file content extraction so the file can be used in context or turned into memory candidates.
  - Store file metadata and link it to conversations or long-term memory.
- **Estimated time (solo founder pace)**: 4-7 days.
- **Dependencies**: Existing file upload infrastructure + Phase 8 (structured memory).

### Phase 12 - Production Hardening and CI

- Goal: Make Rex stable enough for daily founder use without losing data or silently failing.
- Key deliverables:
  - CI for backend tests, Flutter analyze, Flutter tests.
  - Structured logging.
  - Health/readiness endpoints.
  - Integration test mode for real Grok/Supabase smoke tests.
  - Basic monitoring and backup notes.
  - Optional rate limiting and auth if exposed beyond private use.
- Estimated time (solo founder pace): 3-6 days.
- Dependencies: Can run in parallel after Phase 6.

## 6. Immediate Next Actions (Next 48-72 hours)

1. Create `backend/app/services/time_context_service.py`.
   - Add functions to return current server time, timezone label, day of week, ISO timestamp, and human-readable deltas.
   - Add tests in `tests/test_time_context_service.py`.

2. Create `backend/app/services/prompt_service.py`.
   - Move prompt assembly out of `chat_service.py`.
   - Include Rex personality, current time context, recent conversation history, relevant long-term memory, and file context.
   - Add tests in `tests/test_prompt_service.py`.

3. Refactor `backend/app/services/chat_service.py`.
   - Replace `_messages_with_long_term_memory`, `_messages_with_file_context`, and direct prompt assembly with `PromptService`.
   - Keep streaming and non-streaming behavior unchanged.
   - Ensure all existing backend tests still pass.

4. Strengthen `backend/app/services/ai_service.py`.
   - Keep the low-level Grok API responsibility.
   - Move founder-specific personality text out of `AIService.system_prompt` or make it supplied by `PromptService`.
   - Add explicit no-fluff, no-fake-positivity, accountability, and sensitive-life-context behavior in the prompt layer.

5. Draft the Phase 7 Flutter voice implementation skeleton.
   - Create `lib/features/voice/` folders.
   - Decide STT/TTS packages.
   - Add a minimal `VoiceState` model and `VoiceController` plan before UI implementation.

## 7. Revision History

- Date: 2026-05-12 - Initial Alignment Plan created from updated REX_VISION.md
