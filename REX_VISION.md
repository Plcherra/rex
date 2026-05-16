# Rex Vision

## 1. Project Vision

Rex is a private personal AI assistant with long-term memory. It is being built first as the founder's personal daily driver: an uncensored, voice-first, time-aware, memory-powered life co-pilot that knows the ongoing story and gives direct, useful feedback without generic corporate filler. <!-- NEW: founder-first positioning -->

Rex should feel like talking to a maximally honest, human-like, truth-seeking co-pilot. The target personality is Grok-level or better: direct, natural, sharp, and willing to say the uncomfortable thing when it is useful. Rex should not hide behind fake positivity, vague disclaimers, or motivational fluff. It should feel like a real friend who knows the user deeply, remembers the patterns, and holds the user accountable. <!-- NEW: personality and accountability standard -->

Rex should be:

- Direct, honest, and natural.
- Voice-first, with text as the secondary/backup input method.
- Casual enough to feel human, but still useful and grounded.
- Able to remember important personal context across weeks and months.
- Strong at time awareness: it must understand when events happened, how much time has passed, and what has changed since the last conversation.
- Strong at people/entity tracking: it should remember specific people, jobs, plans, rules, recurring topics, and relationship context.
- Useful on sensitive real-life topics: dating life and girl relationships, immigration/visa strategy, money stress, budget failures, work pressure, long-term life plans, frustrations, and daily decisions.
- Private by design, with memory stored in Supabase rather than scattered across third-party chat apps.
- Available through a real Flutter mobile app, not a Telegram bot as the main interface.

The target experience is simple: the founder puts the phone in a pocket, walks, talks naturally, and Rex responds by voice with context-aware advice. If the user says, "Clara touched my arm today," Rex should know who Clara is from previous context, why that matters, and how it fits into the broader dating story. If the user says, "I ordered DoorDash again," Rex should be able to say, directly, "You said last month you were cutting DoorDash because your budget was slipping, and this is the same pattern again." <!-- NEW: real founder use cases -->

Rex should not behave like a blank chatbot every session. It should know:

- Current life situation.
- Important people and relationships.
- Work context, conflicts, goals, and opportunities.
- Immigration status, visa pressure, and related decision timelines.
- Financial pressure, income goals, spending patterns, and personal rules.
- Personal preferences and communication style.
- Recurring frustrations and emotional patterns.
- Important events and decisions.
- Long-term plans, such as income targets, moving countries, rent rules, and deadlines.
- Things the user explicitly asks Rex to remember.

The long-term goal is a voice-capable personal advisor the founder can talk to for hours, including pocket-friendly use while walking and background/lock-screen-friendly workflows where mobile platforms allow it. Public product features can come later; the first priority is a tool that genuinely works for the founder's own life. <!-- NEW: voice-first dogfooding scope -->

## 2. Architecture Overview

High-level flow:

```text
Flutter Mobile App
  |
  |  voice input, text fallback, file/context payloads
  |  - records audio locally and sends it to backend for Deepgram STT
  |  - background/pocket voice workflow where OS allows
  v
FastAPI Backend
  |
  |  cloud voice pipeline:
  |  - Deepgram transcription
  |  - Grok chat/reasoning
  |  - Google Cloud Text-to-Speech playback audio
  |
  |  builds prompt from:
  |  - current server time
  |  - elapsed time since previous relevant events/messages
  |  - current user message or voice transcript
  |  - recent conversation messages
  |  - relevant long-term memory
  |  - tracked entities and personal rules
  |  - temporary file/context input
  |
  +---------------------> Grok API
  |                       |
  |                       v
  |                    AI response
  |
  +<---------------------+
  |
  |  streams response text to Flutter
  |  returns Google TTS audio for playback
  v
Supabase
  |
  |  stores:
  |  - conversations
  |  - messages
  |  - long_term_memory
  |  - future entity records, personal rules, plans, voice metadata,
  |    embeddings, summaries, and time-aware recall data
```

Core responsibilities:

- Flutter owns the user experience: voice-first interaction, microphone recording, text fallback, playback, chat UI, session state, app navigation, mobile polish, and pocket-friendly behavior.
- FastAPI owns orchestration: request validation, current-time injection, time-delta calculation, memory retrieval, entity/context retrieval, prompt assembly, Grok API calls, streaming, and memory writes. <!-- NEW: time-aware orchestration -->
- Deepgram owns production speech-to-text; local Flutter STT remains fallback/dev tooling only. <!-- NEW: cloud voice pipeline -->
- Grok API owns generation: Rex's actual reasoning and conversational response.
- Google Cloud Text-to-Speech owns production spoken output; local Flutter TTS remains fallback/dev tooling only. <!-- NEW: cloud voice pipeline -->
- Supabase owns durable data: conversations, messages, long-term memory, personal rules, entities, plans, and future app data.

The backend should be the only place that talks directly to Grok, Deepgram, Google TTS, and Supabase service-role APIs. The Flutter app should never store Grok, Deepgram, Google, or Supabase service-role secrets.

Voice pipeline target:

```text
User speech
  -> Flutter records compressed audio
  -> FastAPI /voice/transcribe using Deepgram
  -> transcript enters FastAPI /chat streaming pipeline
  -> time-aware prompt + memory/entity/rule context
  -> Grok response
  -> streamed text back to Flutter
  -> FastAPI /voice/synthesize using Google Cloud Text-to-Speech
  -> Flutter plays returned audio
```

The mobile workflow must be designed around walking, phone-in-pocket use, and interrupted real life. Text chat stays valuable, but voice is the primary interface. <!-- NEW: primary interface clarification -->

## 3. Memory System

Rex needs several memory layers: short-term transcript memory, long-term memory, entity memory, personal rules, plans, and time-aware context.

### Short-Term Memory

Short-term memory is the active conversation transcript. It lives in Supabase in the `messages` table and is linked to a `conversation`.

Data saved:

- Conversation id.
- Message id.
- Role: `user` or `assistant`.
- Message content.
- Timestamp.
- Future fields: token count, source type, audio metadata, attachments.

Retrieval behavior:

- On every chat request, fetch the latest messages for the current conversation.
- Keep the prompt under a context budget.
- Prefer the latest messages over older messages.
- Trim old messages when the prompt gets too large.
- Include the timestamp of recent messages so Rex can reason about when things happened.

Purpose:

- Preserve the flow of the current conversation.
- Let Rex answer follow-up questions naturally.
- Avoid forcing the user to repeat context inside the same thread.
- Prevent old context from being treated as if it happened moments ago.

### Long-Term Memory

Long-term memory is durable personal context that should survive across conversations and remain useful across months. It lives in Supabase in the `long_term_memory` table.

Memory types:

- `fact`: stable user facts. Example: "The user works at X", "The user lives in Y", "The user is dealing with immigration paperwork."
- `preference`: user preferences. Example: "The user prefers direct answers", "The user likes concise advice", "The user does not want fake positivity."
- `event`: important life events. Example: "The user had a conflict with a coworker", "The user started a new job", "The user went on a date with someone."

Data saved:

- Memory id.
- Memory type.
- Content.
- Source conversation id.
- Source message id.
- Importance score.
- Active flag.
- Created timestamp.
- Updated timestamp.
- Last accessed timestamp.

Capture behavior:

- Save obvious explicit memory requests, such as "Remember that...".
- Save strong preference statements, such as "I prefer...", "I hate...", "I want...".
- Save stable personal facts, such as "I work...", "I live...", "I have...".
- Save important event statements, such as "I started...", "I moved...", "My birthday is...".
- Use Grok-powered extraction after successful chat turns to identify durable memory candidates.
- Filter extracted candidates by importance and deduplicate them before saving.

Retrieval behavior:

- Before calling Grok, fetch active long-term memories from Supabase using the current user message as retrieval context.
- Rank by keyword overlap, semantic-like text overlap, importance, recency, and time relevance.
- Inject the most relevant memories into the prompt as system context.
- Keep injected memory concise so it does not crowd out the live conversation.

Prompt injection shape:

```text
Current time:
- Server time: 2026-05-12 15:04 America/New_York
- Last message in this conversation: 2 days ago
- Relevant event deltas:
  - Budget reset commitment: 31 days ago
  - Conversation about Clara: 2 days ago

Relevant long-term memory:
- preference: The user prefers direct, practical answers.
- rule: No Uber, Lyft, DoorDash, Nero, or Dunkin. Bom Dough morning coffee only.
- person: Clara is part of the user's current dating context.
- plan: The user wants to reach a monthly income target by a specific date to move out of the country.
```

### Entity Tracking <!-- NEW: explicit entity memory layer -->

Rex must track important entities across time:

- People: Clara, coworkers, friends, girls in the dating context, family members, immigration contacts.
- Jobs and companies.
- Places and routines.
- Long-term plans and deadlines.
- Recurring topics: money, rent, immigration, dating, work, fitness, moving countries.

Entity tracking matters because the founder should be able to speak naturally without re-explaining. If the user mentions "Clara" after several days, Rex should retrieve who Clara is, the latest relevant events, the user's prior interpretation, and any unresolved questions.

### Personal Rules and Accountability <!-- NEW: durable rules and behavioral patterns -->

Rex must permanently remember personal rules and use them for accountability. Examples:

- No Uber/Lyft except true necessity.
- No DoorDash.
- No Nero or Dunkin.
- Bom Dough morning coffee only.
- Grocery caps and rent rules.
- Budget targets and spending limits.

Rex should not merely store these rules. It should notice when behavior violates them and respond directly. If the user repeats a budget failure, Rex should connect the current action to the previous commitment and explain the pattern clearly.

### Time Awareness <!-- NEW: time as required prompt context -->

Time awareness is indispensable. Every response must understand real-world time passage.

The backend must inject:

- Current server time.
- User timezone when known.
- Current date and day of week.
- Time since the last message in the current conversation.
- Time since relevant memories, events, commitments, and plans.
- Deadline deltas for goals and immigration/money plans.

Rex must not treat a conversation from 11pm two days ago as if it is still happening that night. If the user returns two days later at 3pm, Rex should understand that the night has passed, it is now a different afternoon, and the advice should reflect the new context.

### Plans and Multi-Month Goals <!-- NEW: long-horizon planning -->

Rex must handle large plans that unfold over months:

- Income targets by a specific date.
- Moving out of the country.
- Rent decisions.
- Immigration and visa timelines.
- Budget resets and monthly reviews.
- Work and career changes.

These plans should stay alive across sessions without the founder re-explaining them. Rex should periodically surface progress, missed commitments, and next actions.

Future improvements:

- Add embeddings for semantic memory search.
- Add dedicated entity tables for people, places, plans, personal rules, and recurring topics.
- Add memory summaries per topic: work, relationships, money, immigration, goals.
- Improve the current memory review UI with search, grouping, and better explanations for why a memory was recalled.
- Add decay or archival behavior for stale memories.
- Add confidence scores so Rex can distinguish certain facts from guesses.
- Add finance file insights, especially CSV uploads from Clarity, as an optional feature after the voice-first MVP. <!-- NEW: finance CSV future path -->
- Later, explore space awareness when it becomes useful and technically realistic. <!-- NEW: future space awareness -->

## 4. Flutter App Structure

Recommended Flutter structure:

```text
lib/
  main.dart
  core/
    rex_app.dart
    theme/
      app_theme.dart
    config/
      app_config.dart
    networking/
      api_client.dart
  features/
    chat/
      data/
        chat_models.dart
        conversation_api.dart
      domain/
        chat_message.dart
        chat_attachment.dart
      presentation/
        pages/
          chat_page.dart
          conversation_list_page.dart
        widgets/
          chat_input_bar.dart
          chat_message_bubble.dart
          voice_input_button.dart
          typing_indicator.dart
    memory/
      data/
        memory_api.dart
        memory_models.dart
      presentation/
        pages/
          memory_page.dart
          memory_detail_page.dart
        widgets/
          memory_card.dart
          memory_filter_bar.dart
    voice/
      data/
        cloud_voice_api.dart
        audio_recording_service.dart
        audio_playback_service.dart
        audio_session_service.dart
        background_voice_service.dart
        speech_to_text_service.dart   # fallback/dev only
        text_to_speech_service.dart   # fallback/dev only
      presentation/
        widgets/
          voice_recorder_sheet.dart
          audio_playback_controls.dart
          pocket_mode_controls.dart
    settings/
      presentation/
        pages/
          settings_page.dart
```

Main screens:

- Voice-first chat screen: primary Rex interface for speaking and listening.
- Text chat screen: secondary fallback for typed interaction.
- Conversations screen: list of previous chats.
- Memory screen: view, edit, disable, or delete long-term memories.
- Settings screen: backend URL, voice settings, privacy controls, account options later.

Mobile behavior goals:

- Voice input is primary and must feel fast.
- Flutter should record audio and use the FastAPI cloud voice pipeline for production speech-to-text and spoken output. <!-- NEW: production cloud voice -->
- Local Flutter speech-to-text and text-to-speech are fallback/dev tools, not the final street/pocket path. <!-- NEW: production cloud voice -->
- Flutter should send transcripts through FastAPI and play returned Google TTS audio.
- Pocket-friendly workflow is non-negotiable: walking, phone in pocket, screen off/locked/backgrounded where OS rules allow. <!-- NEW: pocket workflow requirement -->
- Push-to-talk comes first, but it must be designed toward background voice calls and locked-screen-friendly interaction.
- Text input remains as a backup for quiet places, debugging, and precision.
- Fast chat rendering with streaming responses.
- Clear loading, speaking, listening, and error states.
- Conversation persistence.
- Keep secrets out of the app. The app calls the FastAPI backend, not Grok directly.

Platform note: iOS and Android impose limits on background recording, wake words, and locked-screen behavior. Rex should push as far as allowed without building fragile hacks. The target is a reliable pocket-friendly workflow, not a demo that only works with the screen open. <!-- NEW: mobile OS constraint -->

## 5. Backend Structure

Recommended backend structure:

```text
backend/
  app/
    main.py
    config.py
    models/
      chat.py
      memory.py
      voice.py
      entity.py
      plan.py
    routes/
      chat.py
      memory.py
      conversations.py
      voice.py
    services/
      ai_service.py
      chat_service.py
      memory_service.py
      memory_extraction_service.py
      entity_service.py
      time_context_service.py
      file_service.py
      voice_service.py
      prompt_service.py
    repositories/
      supabase_client.py
      conversation_repository.py
      message_repository.py
      memory_repository.py
      entity_repository.py
      plan_repository.py
    schemas/
      supabase_schema.sql
  requirements.txt
  .env.example
```

Current key files:

- `app/config.py`: environment settings for Grok and Supabase.
- `app/dependencies.py`: FastAPI dependency providers for injectable services and route tests.
- `app/services/ai_service.py`: Grok API call logic.
- `app/services/memory_service.py`: Supabase memory operations.
- `app/services/memory_extraction_service.py`: Grok-powered long-term memory extraction.
- `app/services/chat_service.py`: orchestrates chat, memory retrieval, prompt assembly, and response persistence.
- `app/routes/chat.py`: FastAPI `/chat` endpoint.
- `app/routes/conversations.py`: conversation list/create/messages/delete endpoints.
- `app/routes/memory.py`: long-term memory list/update/deactivate endpoints.
- `supabase_schema.sql`: database schema for conversations, messages, and long-term memory.

Required backend behavior:

- `chat_service` and future `prompt_service` must always inject current time and relevant time deltas into prompts. <!-- NEW: required backend invariant -->
- Memory retrieval must combine semantic relevance, entity relevance, time relevance, importance, and recency.
- Entity extraction should identify people, places, jobs, plans, rules, and recurring topics.
- Personal rules must be retrieved aggressively when current behavior touches money, transportation, food delivery, rent, coffee, or recurring failure patterns.
- Long-term plans must be retrieved when the current message relates to deadlines, money, immigration, moving, work, or life strategy.
- Voice requests should use the same memory and time-aware prompt pipeline as text requests.

Near-term backend improvements:

- Add `prompt_service.py` to centralize prompt assembly.
- Add `time_context_service.py` to calculate current time, last-message deltas, event deltas, and deadline deltas.
- Add entity and personal-rule storage beyond generic `long_term_memory`.
- Split Supabase HTTP logic into a dedicated Supabase client.
- Move table-specific code into repositories.
- Add semantic retrieval with embeddings once the basic memory pipeline is stable.
- Add CI for backend and Flutter checks.
- Add structured logging and production monitoring.

## 6. Next Steps

### First: Finish Production Readiness

1. Configure real Grok and Supabase environment values.
2. Run `backend/supabase_schema.sql` in Supabase.
3. Test `/chat` against real Grok and real Supabase.
4. Add deployment documentation/configuration for the backend.
5. Deploy the backend on a VPS with a Python virtualenv and `systemd`.
6. Add production HTTPS through Nginx or Caddy.
7. Confirm mobile devices can connect to the deployed backend.

### Second: Phase 6 - Minimal Voice-First Personal Rex <!-- NEW: founder MVP phase -->

1. Keep push-to-talk voice input in Flutter as the primary interface.
2. Use Flutter recording plus Deepgram transcription through FastAPI for production voice input.
3. Send transcripts through the existing FastAPI chat pipeline.
4. Stream Grok responses back to Flutter.
5. Use Google Cloud Text-to-Speech through FastAPI for production spoken responses.
6. Add clear recording, uploading, transcribing, thinking, generating speech, speaking, paused, and failed states.
7. Design the flow for walking with the phone in pocket.
8. Validate locked-screen/background continuation on physical devices within iOS and Android limits.
9. Keep text input and local STT/TTS as backup/dev tooling, not the primary interface.

### Third: Improve Time-Aware Memory Intelligence

1. Add current server time and user timezone to every prompt.
2. Add time deltas since the last conversation, relevant events, commitments, and deadlines.
3. Add entity extraction and retrieval for specific people, jobs, plans, and recurring topics.
4. Add personal-rule memory and accountability behavior.
5. Add embeddings for semantic memory search.
6. Add memory search and grouping in Flutter.
7. Show "why this was recalled" using relevance scores/reasons.
8. Add topic summaries for work, relationships, money, immigration, goals, and daily life.
9. Add confidence and decay behavior for stale memories.

### Fourth: Add Founder Finance and Planning Tools

1. Support CSV uploads from Clarity for finance insight.
2. Track recurring spending failures and budget commitments.
3. Track rent rules, grocery caps, coffee rules, and delivery/ride-share bans.
4. Track monthly income goals and moving-country deadlines.
5. Build monthly and weekly accountability reviews.

The build priority is now clear: make Rex the founder's voice-first daily driver, then make memory time-aware and entity-aware, then deepen accountability and long-term planning.

### Revision History

- 2026-05-12: Updated vision to emphasize founder-first dogfooding, voice-first interaction, uncensored direct personality, time-aware prompt building, entity tracking, personal rules, accountability, and Phase 6 voice-first MVP priorities. <!-- NEW: revision marker -->
- 2026-05-16: Updated voice architecture to make Deepgram + Grok + Google Cloud Text-to-Speech the production street/pocket pipeline, with local STT/TTS kept only as fallback/dev tooling. <!-- NEW: revision marker -->
