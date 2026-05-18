# Active Voice Call Plan

## Goal
Turn Rex voice from a record-stop-reply workflow into an active voice call that feels like a natural conversation.

## Target Streaming Architecture
The final target is a real streaming voice process:

```text
iPhone microphone
-> Flutter streams audio frames continuously
-> FastAPI WebSocket voice session
-> Deepgram live streaming transcription
-> FastAPI emits interim/final transcript events
-> Final user utterance enters PromptService + ChatService
-> Grok streams response tokens
-> Backend chunks response into speakable phrases/sentences
-> Google TTS synthesizes audio chunks as soon as text is ready
-> FastAPI streams audio events back to Flutter
-> iPhone speaker plays chunks while the session stays open
-> Flutter returns to listening without closing the stream
-> Supabase stores messages, memory candidates, and voice-turn metadata
```

## Current Status
The current cloud voice pipeline is working end to end as an automatic endpointing MVP:

```text
iPhone microphone
-> Flutter records a complete utterance
-> FastAPI receives the finished audio file
-> Deepgram transcribes the uploaded audio
-> Grok returns the chat response
-> Google Text-to-Speech synthesizes final response audio
-> iPhone speaker plays the finished response
```

This path is useful as a stable fallback, but it is not the final architecture for a natural street/pocket voice call.

The old manual UX was:

```text
Tap mic -> record -> tap Stop -> transcribe -> think -> synthesize -> play
```

The target UX is active call mode:

```text
Start call
-> Rex listens
-> user speaks
-> Rex detects end of utterance automatically
-> Rex thinks
-> Rex speaks
-> Rex immediately listens again
-> repeat until user ends call
```

## Product Decision
Build active voice call mode before continuing Action Plans 3-7.

Reason: Rex is explicitly voice-first in the vision. The core pipeline now works, so the highest-leverage next step is making voice usable as a real daily driver. Action Plan 3 structured memory is important, but it will be more valuable once the founder can talk to Rex naturally for real sessions.

Recommended order:

```text
1. Active Voice Call Plan
2. Action Plan 3 - Entity, Rule, and Plan Memory Schema
3. Action Plan 4 - Accountability and Pattern Recognition
4. Action Plan 5 - Background & Locked-Screen Voice Continuation
5. Action Plan 6 - General File Upload & Contextual Memory
6. Action Plan 7 - Production Hardening and CI
```

Keep the existing record-stop voice mode as a fallback/debug mode.

## Phase 0 - Stabilize Current Cloud Voice Baseline

### Goal
Lock in the working cloud voice pipeline before changing UX flow.

### Checklist
1. [x] Confirm `https://api.rexpilot.com/ready` reports Grok, Supabase, Deepgram, and Google TTS configured.
2. [x] Confirm `/voice/synthesize` returns `audio/mpeg` from the VPS.
3. [x] Confirm one iPhone voice turn records, transcribes, gets a Grok reply, and speaks audio.
4. [x] Mark cloud voice path complete in `docs/action_plans/vps_deployment_checklist.md`.
5. [x] Keep record-stop mode as fallback and do not remove it during active-call work.

### Verification
```sh
curl -s https://api.rexpilot.com/ready | python3 -m json.tool
curl -s -X POST https://api.rexpilot.com/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Rex voice playback is configured."}' | python3 -m json.tool
```

## Phase 1 - Add Active Call State Model

### Goal
Create explicit call-mode state separate from one-shot voice recording state.

### Files
- `lib/features/voice/domain/voice_call_state.dart`
- `lib/features/voice/application/voice_call_controller.dart`
- `lib/core/providers.dart`
- Existing voice tests under `test/features/voice/`

### Required States
- `idle`
- `starting`
- `listening`
- `capturingSpeech`
- `endpointing`
- `transcribing`
- `thinking`
- `speaking`
- `interrupted`
- `failed`
- `ended`

### Checklist
1. [x] Create a dedicated `VoiceCallState` model.
2. [x] Create a dedicated `VoiceCallController`.
3. [x] Track current transcript, last assistant response, call duration, current conversation id, error message, and whether the call is active.
4. [x] Keep the existing `VoiceController` for one-shot record mode.
5. [x] Add unit tests for state transitions.

### Verification
```sh
flutter analyze
flutter test test/features/voice
```

## Phase 2 - Build Active Call Screen

### Goal
Replace the bottom-sheet feel with a real call interface.

### Files
- `lib/features/voice/presentation/pages/voice_call_page.dart`
- `lib/features/chat/presentation/pages/chat_page.dart`
- `lib/features/voice/presentation/widgets/voice_call_controls.dart`

### Checklist
1. [x] Add a “Call Rex” entry point from `ChatPage`.
2. [x] Build a full-screen call UI with clear listening/thinking/speaking states.
3. [x] Show live transcript and latest Rex response.
4. [x] Add controls: end call, mute mic, interrupt Rex, retry after failure.
5. [x] Keep the normal chat UI visible after call ends with the conversation history updated.

### Verification
```sh
flutter analyze
flutter test test/features/voice
```

## Phase 3 - Implement Automatic Endpointing MVP

### Goal
Remove the manual Stop button for normal use.

### First MVP Approach
Use local audio recording plus simple silence detection / max-duration rules:

```text
start listening
-> record audio locally
-> detect silence after speech
-> stop current utterance automatically
-> upload utterance to /voice/turn or /voice/transcribe
```

This is simpler than full streaming STT and good enough for the first active-call MVP.

### Files
- `lib/features/voice/data/audio_capture_service.dart`
- `lib/features/voice/application/voice_call_controller.dart`
- Existing cloud voice API files

### Checklist
1. [x] Capture audio while call mode is listening.
2. [x] Detect speech start using amplitude threshold.
3. [x] Detect end of utterance after configurable silence, such as 900-1400 ms.
4. [x] Add max utterance duration, such as 45-60 seconds.
5. [x] Handle empty/noisy captures without sending useless requests.
6. [x] Add settings constants for silence threshold and duration.

### Verification
```sh
flutter analyze
flutter test test/features/voice
```

## Phase 4 - Add Listen-Think-Speak-Listen Loop

### Goal
Make the automatic endpointing call continue across turns while preparing the boundary for the real streaming transport.

### Files
- `lib/features/voice/application/voice_call_controller.dart`
- `lib/features/voice/data/cloud_voice_api.dart`
- `lib/features/chat/application/chat_controller.dart`

### Checklist
1. [x] After endpointing, send the utterance through the existing cloud voice/chat pipeline.
2. [x] When Rex starts thinking, stop mic capture to avoid echo.
3. [x] When TTS audio starts, enter `speaking`.
4. [x] When audio playback completes, automatically return to `listening`.
5. [x] Store every voice turn in the same conversation thread.
6. [x] Keep UI responsive if network calls take several seconds.
7. [x] Keep call state names compatible with the later WebSocket streaming session.

### Verification
```sh
flutter analyze
flutter test
```

## Phase 5 - Add Interrupt and Barge-In Behavior

### Goal
Let the founder stop Rex mid-answer and speak again naturally.

### Files
- `lib/features/voice/application/voice_call_controller.dart`
- `lib/features/voice/data/audio_playback_service.dart`
- `lib/features/voice/presentation/pages/voice_call_page.dart`

### Checklist
1. [x] Add an interrupt button that stops current TTS playback.
2. [x] After interrupting, immediately return to listening.
3. [x] Prevent stale TTS completion callbacks from changing state after interruption.
4. [x] Add optional tap-and-hold-to-speak while Rex is speaking.
5. [x] Add tests for interruption during thinking and speaking.

### Verification
```sh
flutter analyze
flutter test test/features/voice
```

## Phase 6 - Replace Upload Turns With Streaming Voice Transport

### Goal
Move from upload-per-turn voice calls to a persistent WebSocket session that streams audio and receives transcript/audio events.

### Target Streaming Flow
```text
Flutter opens WebSocket /voice/stream
-> Flutter sends session.start
-> Flutter sends small microphone audio frames
-> FastAPI forwards frames to Deepgram streaming STT
-> FastAPI sends transcript.partial events to Flutter
-> Deepgram final transcript triggers Grok streaming
-> FastAPI sends assistant.token events to Flutter
-> Backend chunks completed phrases/sentences for Google TTS
-> FastAPI sends assistant.audio_chunk events to Flutter
-> Flutter queues and plays audio chunks
-> session stays open for the next utterance
```

### Files
- `backend/app/routes/voice_stream.py`
- `backend/app/services/deepgram_streaming_service.py`
- `backend/app/services/voice_stream_session.py`
- `backend/app/routes/voice.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/prompt_service.py`
- `lib/features/voice/data/streaming_voice_api.dart`
- `lib/features/voice/data/streaming_audio_capture_service.dart`
- `lib/features/voice/data/streaming_audio_playback_queue.dart`
- `lib/features/voice/data/cloud_voice_api.dart`
- `lib/features/voice/application/voice_call_controller.dart`

### Checklist
1. [x] Add backend `WebSocket /voice/stream`.
2. [x] Add a typed event contract: `session.started`, `audio.received`, `transcript.partial`, `transcript.final`, `assistant.token`, `assistant.audio_chunk`, `assistant.done`, `error`.
3. [x] Implement Deepgram live streaming service behind FastAPI so Deepgram secrets stay server-side.
4. [x] Stream microphone frames from Flutter instead of recording full files.
5. [x] Feed final transcripts into the existing PromptService + ChatService memory path.
6. [x] Stream Grok response tokens back to Flutter.
7. [x] Add phrase/sentence chunking so Google TTS can begin before the whole answer is done.
8. [x] Stream or queue Google TTS audio chunks back to Flutter as soon as each chunk is synthesized.
9. [x] Keep `/voice/turn` and record-stop mode as fallback.
10. [x] Add timing metrics for STT latency, Grok first token, first audio chunk, and full turn completion.

### Implementation Note
Phase 6 is implemented as an opt-in streaming path behind `REX_STREAMING_VOICE_ENABLED=true`. The backend WebSocket supports repeated utterances on one session; the Flutter call controller can use the stream transport but still keeps the stable `/voice/turn` path as the default fallback until Phase 6.5 hardens streaming playback, persistent session reuse, and barge-in cancellation.

### Verification
```sh
PYTHONPATH=backend python3 -m pytest -q tests/test_voice_stream_routes.py tests/test_voice_routes.py
flutter test test/features/voice
```

## Phase 6.5 - Streaming Playback and Barge-In

### Goal
Make Rex feel like a live call: audio starts quickly, the user can interrupt, and the system can resume listening without closing the session.

### Files
- `lib/features/voice/data/streaming_audio_playback_queue.dart`
- `lib/features/voice/application/voice_call_controller.dart`
- `lib/features/voice/presentation/pages/voice_call_page.dart`
- `backend/app/services/voice_stream_session.py`

### Checklist
1. [x] Queue incoming audio chunks in Flutter and play them in order.
2. [x] Cancel queued audio when the user interrupts Rex.
3. [x] Send `user.interrupt` over the WebSocket to cancel backend Grok/TTS work.
4. [x] Prevent stale audio chunks from previous responses from playing after interruption.
5. [x] Return to listening immediately after interruption.
6. [x] Add tests for token streaming, audio chunk ordering, and interruption.

### Implementation Note
Flutter now uses `StreamingAudioPlaybackQueue` to play streamed Google TTS chunks sequentially and cancel stale queued audio on interruption. Normal streaming turns keep the WebSocket session open for the next utterance. The backend `/voice/stream` session now processes each utterance in a cancellable task, so `user.interrupt` can stop in-progress Deepgram/Grok/TTS work instead of waiting for the full response to finish. The streaming path remains opt-in behind `REX_STREAMING_VOICE_ENABLED=true`.

### Verification
```sh
flutter test test/features/voice
PYTHONPATH=backend python3 -m pytest -q tests/test_voice_stream_routes.py
```

## Phase 7 - Phone and Street Validation

### Goal
Prove active call mode works outside the simulator and outside a quiet desk setup.

### Checklist
1. [ ] Test on real iPhone over Wi-Fi.
2. [ ] Test on real iPhone over cellular.
3. [ ] Test with AirPods or Bluetooth headset.
4. [ ] Test walking outside with street noise.
5. [ ] Test app switching while call is active.
6. [ ] Document latency, transcription quality, and failure cases.
7. [ ] Update `docs/action_plans/vps_deployment_checklist.md`.

### Verification
Manual iPhone test with VPS logs open:

```sh
sudo journalctl -u rex-backend -f
```

## Phase 8 - Prepare for Background and Locked-Screen Mode

### Goal
Make Action Plan 5 easier by separating foreground call logic from OS background behavior.

### Checklist
1. [ ] Keep active call controller independent from the call screen widget lifecycle.
2. [ ] Keep audio session setup centralized.
3. [ ] Document what breaks when the app backgrounds.
4. [ ] Add notes for iOS `AVAudioSession`, background audio mode, interruptions, and route changes.
5. [ ] Defer true locked-screen continuation to Action Plan 5.

## Definition of Done
- [ ] Founder can tap “Call Rex” once and have a multi-turn spoken conversation.
- [ ] No manual Stop button is required for normal conversation.
- [ ] Rex automatically returns to listening after speaking.
- [ ] Founder can interrupt Rex mid-answer.
- [ ] Record-stop mode still exists as fallback.
- [ ] iPhone Wi-Fi and cellular tests pass.
- [ ] Known latency is measured and documented.

## Revision History
- 2026-05-17 - Active voice call plan created after production Deepgram, Grok, and Google TTS pipeline became functional.
