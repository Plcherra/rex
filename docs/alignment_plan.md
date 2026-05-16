# REX Alignment Plan

## 1. Executive Summary

Rex is roughly **7/10 aligned** with the updated founder vision overall, and closer to **7/10 aligned** with the voice-first daily-driver requirement at the code level. The strongest foundation is now in place: Flutter chat UI, FastAPI backend, Grok API integration, streaming responses, Supabase-backed conversations/messages/long-term memory, memory UI, file upload support, cloud voice with Deepgram + Google TTS, background audio/foreground-service scaffolding, tests, and VPS deployment docs. The biggest remaining risks are physical street/pocket validation, structured entity/rule/plan memory, deeper accountability logic, production monitoring, and real-device platform constraints. The project is no longer blocked by missing voice infrastructure; it is now blocked by physical device validation and deeper memory intelligence.

## 2. Vision vs Reality Matrix

| Vision Section / Requirement | Current Implementation Status (Fully Done / Partially Done / Not Started / Needs Refactor) | Key Files / Code Involved | Gap Description & Technical Reason | Effort Estimate (Small / Medium / Large / Unknown) | Priority (P0 / P1 / P2) |
|---|---|---|---|---|---|
| Founder-first personal daily driver | Partially Done | `REX_VISION.md`, `README.md`, `docs/deployment.md` | Project direction and docs now say founder-first, but product behavior still mostly behaves like a generic chat app with memory. No founder-specific rules, plans, entities, or accountability layer exists. | Medium | P0 |
| Voice-first primary interface | Partially Done | `lib/features/voice/`, `lib/features/chat/presentation/widgets/chat_input_bar.dart`, `backend/app/routes/voice.py` | Push-to-talk voice UI, controller state machine, cloud transcription, cloud synthesis, and playback exist. It still needs real iPhone/Android street validation and UX tuning from physical use. | Medium | P0 |
| Pocket / locked-screen / background voice workflow | Partially Done | `ios/Runner/Info.plist`, `android/app/src/main/AndroidManifest.xml`, `android/app/src/main/kotlin/com/rex/rex/RexVoiceForegroundService.kt`, `lib/features/voice/data/audio_session_service.dart`, `docs/background_voice_constraints.md` | iOS background audio mode, Android foreground service, audio session handling, and interruption handling are implemented. Actual reliability is still unknown until physical device testing because OS rules decide final behavior. | Medium / Unknown | P0 |
| Flutter speech-to-text pipeline | Fully Done | `lib/features/voice/data/audio_recording_service.dart`, `lib/features/voice/data/cloud_voice_api.dart`, `backend/app/services/deepgram_service.py`, `backend/app/routes/voice.py` | Production STT is cloud-based through Deepgram. Local `speech_to_text_service.dart` remains fallback/dev tooling only. | Small for tuning | P0 |
| Flutter text-to-speech playback | Fully Done | `lib/features/voice/data/audio_playback_service.dart`, `lib/features/voice/data/cloud_voice_api.dart`, `backend/app/services/google_tts_service.py`, `backend/app/routes/voice.py` | Production TTS uses Google Cloud TTS through FastAPI and plays returned audio in Flutter. Local `text_to_speech_service.dart` remains fallback/dev tooling only. | Small for tuning | P0 |
| Streaming text chat | Fully Done | `lib/services/chat_api.dart`, `lib/features/chat/application/chat_controller.dart`, `backend/app/routes/chat.py`, `backend/app/services/ai_service.py`, `backend/app/services/chat_service.py` | SSE streaming exists, Flutter progressively renders assistant tokens, and voice uses the same chat pipeline before Google TTS synthesis. | Small for polish | P0 |
| Text chat fallback | Fully Done | `lib/features/chat/presentation/pages/chat_page.dart`, `lib/features/chat/presentation/widgets/chat_input_bar.dart`, `lib/services/chat_api.dart` | Text chat is functional, supports loading/error states, streaming, conversations, and file attachments. | Small | P1 |
| Conversation management | Fully Done | `backend/app/routes/conversations.py`, `lib/features/chat/presentation/pages/conversation_list_page.dart`, `lib/features/chat/application/conversation_controller.dart` | List/create/switch/delete are implemented with tests. Needs future UX polish but meets current requirement. | Small | P1 |
| Long-term memory across months | Partially Done | `backend/supabase_schema.sql`, `backend/app/services/memory_service.py`, `backend/app/services/memory_extraction_service.py`, `lib/features/memory/` | `long_term_memory` stores durable memories with timestamps and active flag. Retrieval is basic keyword/concept scoring, not true month-scale semantic memory with summaries, plans, or entities. | Large | P0 |
| Memory UI for review/edit/deactivate | Partially Done | `lib/features/memory/presentation/pages/memory_page.dart`, `backend/app/routes/memory.py` | User can list/edit/deactivate facts/preferences/events. No search, grouping, entity view, plan view, personal rules view, or “why recalled” UI. | Medium | P1 |
| Grok-powered memory extraction | Partially Done | `backend/app/services/memory_extraction_service.py` | Extraction exists for `fact`, `preference`, `event`. Prompt does not yet extract entities, rules, plans, deadlines, commitments, or relationship-specific context into structured tables. | Medium | P0 |
| Query-aware memory retrieval | Partially Done | `backend/app/services/memory_service.py` | Keyword + concept overlap + importance + recency exists. No embeddings, vector search, entity joins, plan retrieval, personal-rule boosting, or time-delta-aware scoring. | Large | P0 |
| Time awareness: current server time in every prompt | Fully Done | `backend/app/services/time_context_service.py`, `backend/app/services/prompt_service.py`, `backend/app/services/chat_service.py`, `tests/test_time_context_service.py`, `tests/test_prompt_service.py` | Every Grok call receives explicit server time, timezone, weekday, conversation timestamp metadata, and session-gap context through `PromptService`. | Small for tuning | P0 |
| Time deltas since messages/events/commitments | Partially Done | `backend/app/services/time_context_service.py`, `backend/app/services/prompt_service.py`, `backend/app/services/memory_service.py` | Session gaps and memory ages are injected. Commitment/deadline deltas still need structured commitments/plans before they can be reliable. | Medium | P0 |
| Prompt assembly as explicit service | Fully Done | `backend/app/services/prompt_service.py`, `backend/app/services/chat_service.py`, `backend/app/services/ai_service.py` | Prompt composition, Rex personality, time context, memory context, file context, and conversation metadata are centralized in `PromptService`. | Small for tuning | P0 |
| Entity tracking: people like Clara/Melissa, jobs, plans | Not Started | Missing `entity_service.py`, `entity_repository.py`, Supabase entity tables | Current memory is unstructured text with `fact/preference/event`. No entity table, alias handling, relationship context, timeline per person, or retrieval by entity mention exists. | Large | P0 |
| Personal rules: no Uber, Bom Dough only, budget caps | Not Started | Missing personal rules schema/service/UI | Rules may be saved as generic memories if Grok extracts them, but there is no durable rule type, enforcement/retrieval priority, violation detection, or accountability logic. | Large | P0 |
| Accountability and pattern recognition | Not Started | Missing accountability service, plan/rule models, finance pattern logic | Rex cannot detect “you promised this last month” except if a generic memory happens to be retrieved. Needs commitments, rules, event timelines, and behavior comparisons. | Large | P0 |
| Multi-month plans and progress tracking | Not Started | Missing plan schema/service/UI | No plan table, milestones, target dates, progress state, deadline deltas, or periodic review logic. Current `long_term_memory` cannot reliably maintain active plans. | Large | P0 |
| Uncensored / human-like / Grok-level personality | Partially Done | `backend/app/services/ai_service.py` | System prompt is direct and concise, but not founder-specific enough. It does not explicitly encode no-BS accountability, sensitive life topics, voice style, personal rules, or truth-seeking behavior. | Small / Medium | P0 |
| Sensitive real-life advice topics | Partially Done | `backend/app/services/ai_service.py`, `backend/app/services/memory_extraction_service.py` | Current prompt allows practical direct advice, and memory extraction mentions legal/financial/relationship context. But no specific founder domains are modeled: dating context, immigration strategy, money patterns, or personal constraints. | Medium | P0 |
| Supabase schema for conversations/messages/memory | Fully Done | `backend/supabase_schema.sql` | Core chat and generic memory schema exists and is usable. | Small | P1 |
| Supabase schema for entities/rules/plans | Not Started | `backend/supabase_schema.sql` | No `entities`, `entity_events`, `personal_rules`, `plans`, `plan_milestones`, or `commitments` tables exist. | Medium / Large | P0 |
| Voice metadata storage | Partially Done | `backend/supabase_schema.sql`, `backend/app/models/voice.py`, `backend/app/routes/voice.py`, `backend/app/services/chat_service.py` | `voice_turns` storage and voice request/response models exist. More device-state metadata and playback quality data can be added after physical tests. | Small / Medium | P1 |
| CSV/file upload, including Clarity finance CSV | Partially Done | `backend/app/services/file_service.py`, `lib/features/chat/domain/chat_attachment.dart`, `lib/features/chat/presentation/pages/chat_page.dart` | `.csv` upload is supported as text context. No Clarity-specific parser, finance insight service, recurring merchant detection, or budget review pipeline. | Medium | P1 |
| Space awareness later | Not Started | No code | Correctly future-only. No action needed for MVP. | Unknown | P2 |
| Privacy: secrets not in app | Fully Done | `lib/core/config/app_config.dart`, `backend/app/config.py`, `.gitignore`, docs | Flutter uses backend URL only. Grok/Supabase service keys stay backend-side. `.env` is ignored. | Small | P0 |
| Deployment readiness | Partially Done | `docs/deployment.md`, `backend/app/main.py`, `backend/app/config.py`, `README.md` | VPS deployment docs, lifespan handler, CORS, and env handling exist. Still missing actual systemd file, production logging, monitoring, health checks beyond `/`, and CI. | Medium | P1 |
| Test coverage | Partially Done | `tests/`, `test/` | Good service/route/widget coverage: backend 116 tests, Flutter 68 tests. Voice route/service/controller/widget tests exist. Still missing real-vendor smoke tests, physical-device voice acceptance logs, entity tests, and plan/rule tests. | Medium | P1 |
| Backend async reliability | Fully Done | `backend/app/services/http_client.py`, `backend/app/services/ai_service.py`, `backend/app/services/memory_service.py` | Grok and Supabase use async `httpx`. Shared HTTP lifecycle exists. | Small | P1 |
| Mobile UX polish for current chat | Partially Done | `lib/features/chat/presentation/pages/chat_page.dart`, `lib/features/chat/presentation/widgets/chat_message_bubble.dart`, `lib/features/voice/presentation/widgets/voice_recorder_sheet.dart` | Text chat and voice sheet are polished enough for continued development. Real street/pocket UX still needs device testing and tuning. | Medium | P1 |

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
- Production cloud voice exists: Flutter recording, Deepgram transcription, Grok chat, Google TTS synthesis, and Flutter audio playback.
- Background/pocket scaffolding exists: iOS background audio mode, Android foreground service, audio session handling, and interruption recovery.
- Deployment path is clean for VPS: virtualenv, `systemd`, Nginx/Caddy, env vars, CORS, and HTTPS guidance.
- Test coverage is strong for the current scope: backend route/service tests and Flutter API/controller/widget tests are in place.

## 4. Critical Gaps & Why They Exist

The largest remaining voice gap is physical street/pocket validation. The cloud voice pipeline exists, but iOS and Android background behavior must be tested on real devices with screen lock, app switching, Bluetooth/headphones, noisy street conditions, and interruptions. Simulators and unit tests cannot prove the final founder workflow.

The second critical gap is structured memory depth, not basic time awareness. Current server time, session gaps, and memory ages are now injected through `PromptService` and `TimeContextService`, but Rex still lacks first-class entities, personal rules, commitments, and plans. Without those records, time deltas for “you promised this last month” or “this deadline is 31 days away” remain unreliable.

The third critical gap is the lack of structured entity, rule, and plan storage. `long_term_memory` can hold generic facts, preferences, and events, but the updated vision requires Rex to remember specific people, recurring relationship context, personal rules, commitments, deadlines, and multi-month plans. Those need first-class schema and services, not just text memories. Without this, accountability will be unreliable and retrieval will be too dependent on keyword overlap.

The fourth critical gap is accountability logic. Rex currently retrieves memories and sends them to Grok, but it does not detect rule violations, compare current behavior to past commitments, run budget pattern checks, or surface missed plan milestones. The project needs explicit `personal_rules`, `commitments`, and `plans` models plus retrieval/violation logic before Rex can say, accurately, “you said you would stop doing this last month.”

The fifth gap is deeper personality grounding against structured facts. `PromptService` now owns the founder-first personality and direct/no-fluff behavior, but the personality will only become truly accountable once entities, rules, commitments, and plans are first-class memory records.

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

- Goal: Keep Rex usable as a voice-first personal assistant in foreground mode using the production cloud voice path.
- Key deliverables:
  - Flutter records microphone audio and uploads it to FastAPI.
  - FastAPI transcribes through Deepgram.
  - Transcript enters the existing `/chat` streaming pipeline with Grok.
  - FastAPI synthesizes the final response through Google Cloud TTS.
  - Flutter plays returned audio and exposes recording/uploading/transcribing/thinking/generating/speaking states.
  - Local STT/TTS stays available only as fallback/dev tooling.
- Estimated time (solo founder pace): implemented; continue tuning from physical tests.
- Dependencies: Phase 6 prompt foundation and backend cloud voice routes.

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
  - Configure proper audio session categories, iOS background audio, and Android foreground service behavior.
  - Handle interruptions (incoming calls, notifications, headphones, screen lock).
  - Ensure the production cloud voice flow (recording → Deepgram transcription → Grok thinking → Google TTS speaking) survives app backgrounding and screen off where possible.
  - Add clear UX feedback when background continuation is limited by the OS.
  - Document realistic platform constraints.
- **Estimated time (solo founder pace)**: implementation scaffold complete; physical validation and tuning still required.
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

1. Run the physical iPhone street/pocket acceptance test.
   - Test lock screen, app switching, AirPods/Bluetooth, noisy street, long monologue, interruption, and a second turn.
   - Record exact failures in `docs/background_voice_constraints.md` or a follow-up checklist.

2. Run the physical Android street/pocket acceptance test.
   - Verify foreground notification, microphone survival, audio focus, headphones, app switch, and screen lock behavior.
   - Decide whether Android notification permission UX needs an explicit in-app prompt.

3. Tighten any issues found during physical voice testing.
   - Likely files: `lib/features/voice/application/voice_controller.dart`, `lib/features/voice/data/audio_session_service.dart`, `android/app/src/main/AndroidManifest.xml`, `ios/Runner/Info.plist`.
   - Keep `flutter analyze`, `flutter test`, and backend tests green.

4. Continue structured memory work.
   - Add `entities`, `entity_events`, `personal_rules`, `plans`, `plan_milestones`, and `commitments`.
   - Update extraction and retrieval to make accountability reliable.

5. Add production hardening.
   - CI, structured logs, real-vendor smoke test mode, backup/restore notes, and basic monitoring.

## 7. Revision History

- Date: 2026-05-12 - Initial Alignment Plan created from updated REX_VISION.md
- Date: 2026-05-16 - Updated after cloud voice implementation: Deepgram + Grok + Google TTS pipeline, background scaffolding, and current test counts.
