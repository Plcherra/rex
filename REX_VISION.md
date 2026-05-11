# Rex Vision

## 1. Project Vision

Rex is a private personal AI assistant with long-term memory. It should feel like talking to someone who actually knows the user, understands the ongoing story of their life, and gives direct, useful advice without generic corporate filler.

Rex should be:

- Direct, honest, and natural.
- Casual enough to feel human, but still useful and grounded.
- Able to remember important personal context across days, weeks, and months.
- Built for long conversations over text and eventually voice.
- Private by design, with the user's memory stored in Supabase rather than scattered across third-party chat apps.
- Available through a real Flutter mobile app, not a Telegram bot as the main interface.

The target experience is simple: open the Rex app, talk naturally, and Rex already knows the relevant context. If the user talks about work stress, girls, money, immigration, personal goals, daily events, or frustrations, Rex should connect that to previous conversations and respond with context-aware advice.

Rex should not behave like a blank chatbot every session. It should know:

- Current life situation.
- Important people and relationships.
- Work context, conflicts, goals, and opportunities.
- Immigration status and related stress.
- Financial pressure, income goals, and spending patterns.
- Personal preferences.
- Recurring frustrations and emotional patterns.
- Important events and decisions.
- Things the user explicitly asks Rex to remember.

The long-term goal is a voice-capable personal advisor that the user can talk to for hours, including hands-free use and eventually support for background or lock-screen-friendly workflows where the mobile platform allows it.

## 2. Architecture Overview

High-level flow:

```text
Flutter Mobile App
  |
  |  text, voice transcript, file/context payloads
  v
FastAPI Backend
  |
  |  builds prompt from:
  |  - current user message
  |  - recent conversation messages
  |  - relevant long-term memory
  |  - temporary file/context input
  |
  +---------------------> Grok API
  |                       |
  |                       v
  |                    AI response
  |
  v
Supabase
  |
  |  stores:
  |  - conversations
  |  - messages
  |  - long_term_memory
  |  - future voice metadata, user profile, embeddings, summaries
```

Core responsibilities:

- Flutter owns the user experience: chat UI, voice input, playback, session state, app navigation, and mobile polish.
- FastAPI owns orchestration: request validation, memory retrieval, prompt assembly, Grok API calls, and memory writes.
- Grok API owns generation: Rex's actual reasoning and conversational response.
- Supabase owns durable data: conversations, messages, long-term memory, and future app data.

The backend should be the only place that talks directly to Grok using the API key. The Flutter app should never store Grok or Supabase service-role secrets.

## 3. Memory System

Rex needs two major memory layers: short-term memory and long-term memory.

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

Purpose:

- Preserve the flow of the current conversation.
- Let Rex answer follow-up questions naturally.
- Avoid forcing the user to repeat context inside the same thread.

### Long-Term Memory

Long-term memory is durable personal context that should survive across conversations. It lives in Supabase in the `long_term_memory` table.

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
- Later, add an AI-based memory extraction step so Rex can identify important memories more intelligently than simple rules.

Retrieval behavior:

- Before calling Grok, fetch active long-term memories from Supabase.
- Rank by importance, recency, and relevance.
- Inject the most relevant memories into the prompt as system context.
- Keep injected memory concise so it does not crowd out the live conversation.

Prompt injection shape:

```text
Relevant long-term memory:
- preference: The user prefers direct, practical answers.
- fact: The user is focused on building Rex as a personal AI assistant.
- event: The user recently removed Ollama and SQLite from the project.
```

Future improvements:

- Add embeddings for semantic memory search.
- Add memory summaries per topic: work, relationships, money, immigration, goals.
- Add memory review UI so the user can edit or delete what Rex remembers.
- Add decay or archival behavior for stale memories.
- Add confidence scores so Rex can distinguish certain facts from guesses.

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
        chat_api.dart
        chat_models.dart
      domain/
        chat_message.dart
        conversation.dart
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
        voice_service.dart
      presentation/
        widgets/
          voice_recorder_sheet.dart
          audio_playback_controls.dart
    settings/
      presentation/
        pages/
          settings_page.dart
```

Main screens:

- Chat screen: primary Rex interface for text and voice.
- Conversations screen: list of previous chats.
- Memory screen: view, edit, disable, or delete long-term memories.
- Settings screen: backend URL, voice settings, privacy controls, account options later.

Mobile behavior goals:

- Fast chat input with smooth message rendering.
- Voice input button in the composer.
- Clear loading and error states.
- Conversation persistence.
- Push-to-talk first, then more advanced hands-free voice mode later.
- Keep secrets out of the app. The app calls the FastAPI backend, not Grok directly.

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
    routes/
      chat.py
      memory.py
      conversations.py
      voice.py
    services/
      ai_service.py
      chat_service.py
      memory_service.py
      file_service.py
      voice_service.py
      prompt_service.py
    repositories/
      supabase_client.py
      conversation_repository.py
      message_repository.py
      memory_repository.py
    schemas/
      supabase_schema.sql
  requirements.txt
  .env.example
```

Current key files:

- `app/config.py`: environment settings for Grok and Supabase.
- `app/services/ai_service.py`: Grok API call logic.
- `app/services/memory_service.py`: Supabase memory operations.
- `app/services/chat_service.py`: orchestrates chat, memory retrieval, prompt assembly, and response persistence.
- `app/routes/chat.py`: FastAPI `/chat` endpoint.
- `supabase_schema.sql`: database schema for conversations, messages, and long-term memory.

Near-term backend improvements:

- Split Supabase HTTP logic into a dedicated Supabase client.
- Move table-specific code into repositories.
- Add `memory.py` models for typed memory responses.
- Add `/memory` endpoints so the Flutter app can list, edit, deactivate, and delete memories.
- Add better memory extraction using Grok instead of only rule-based detection.
- Add semantic retrieval with embeddings once the basic memory pipeline is stable.

## 6. Next Steps

### First: Make Core Chat Fully Real

1. Configure real Grok and Supabase environment values.
2. Run `backend/supabase_schema.sql` in Supabase.
3. Test `/chat` against real Grok and real Supabase.
4. Wire the Flutter chat page to the backend.
5. Persist and reuse `conversation_id` in the Flutter app.
6. Show real user and assistant messages in the UI.
7. Add loading, retry, and error states.

### Second: Make Memory Visible and Editable

1. Add backend `/memory` routes.
2. Add memory list, update, deactivate, and delete operations.
3. Build a Flutter Memory screen.
4. Let the user inspect what Rex remembers.
5. Let the user delete wrong or sensitive memories.
6. Add memory type filters: facts, preferences, events.

### Third: Improve Memory Intelligence and Voice

1. Replace simple memory extraction rules with a Grok-powered extraction step.
2. Add relevance scoring for long-term memory retrieval.
3. Add embeddings for semantic memory search.
4. Add voice input in Flutter.
5. Add assistant voice playback.
6. Explore background and lock-screen-friendly behavior within mobile platform limits.
7. Add topic summaries for work, relationships, money, immigration, goals, and daily life.

The build priority is clear: first make chat work end to end, then make memory trustworthy and editable, then make Rex smarter and more natural through better retrieval and voice.
