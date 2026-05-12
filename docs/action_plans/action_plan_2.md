# Action Plan 2 - Minimal Voice-First Personal Rex

## Goal
Make Rex usable as a voice-first personal assistant in foreground mode first.

## Why This Matters (Personal Context)
This is the phase where Rex finally becomes what the founder actually needs: a true voice-first co-pilot. The founder wants to talk to Rex while walking with the phone in their pocket, get real-time responses, and hear the answer spoken back -- all without having to look at the screen or type. This transforms Rex from a text chat app into the daily hands-free companion that remembers time gaps, personal rules, dating context, immigration plans, and budget accountability.

## Key Deliverables
- Add Flutter STT dependency and permission flow
- Add Flutter TTS dependency and playback service
- Create `lib/features/voice/` with `voice_service.dart`, `speech_to_text_service.dart`, `text_to_speech_service.dart`, and `voice_recorder_sheet.dart`
- Add push-to-talk button and voice state UI: idle, listening, transcribing, thinking, speaking, failed
- Send transcript through the existing `/chat` streaming pipeline
- Speak streamed/final assistant response
- Add widget/controller tests for voice state transitions where practical

## Estimated Time
4-7 focused days (solo founder pace) for a usable foreground MVP

## Dependencies
Action Plan 1 (Time-Aware Prompt Foundation) must be 100% complete first so voice uses the correct prompt intelligence and personality.

## Checklist (10 Actionable Steps)

1. [ ] **Choose voice packages and add Flutter dependencies**
   - Exact files to create or modify: `pubspec.yaml`, `pubspec.lock`
   - What must be implemented: Add production-ready packages for speech-to-text, text-to-speech, microphone permission handling, and audio session management. Recommended starting point: `speech_to_text`, `flutter_tts`, `permission_handler`, and `audio_session`.
   - Success criteria: Dependencies resolve cleanly, the app still builds, and no existing chat or memory imports break.
   - Verification / test command: `flutter pub get && flutter analyze && flutter test`
   - Suggested git commit message: `chore: add voice dependencies`
   - Rough time estimate: 1-2 hours

2. [ ] **Create the voice feature folder and state model**
   - Exact files to create or modify: `lib/features/voice/domain/voice_state.dart`, `lib/features/voice/application/voice_controller.dart`, optionally `lib/core/providers.dart`
   - What must be implemented: Define voice states for idle, listening, transcribing, thinking, speaking, failed, and permissionDenied. Include fields for partial transcript, final transcript, spoken response text, error message, and whether Rex is currently busy.
   - Success criteria: Voice state is explicit, testable, and does not rely on widget-local booleans for core behavior.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add voice state model`
   - Rough time estimate: 2-3 hours

3. [ ] **Implement microphone permission flow**
   - Exact files to create or modify: `lib/features/voice/application/voice_controller.dart`, platform files under `ios/Runner/Info.plist`, `android/app/src/main/AndroidManifest.xml`
   - What must be implemented: Request microphone permission before listening, handle denied/permanently denied states, and expose friendly state for the UI to show when permission is missing.
   - Success criteria: Rex never attempts to start listening without permission, and denied permission produces a clear recoverable UI state.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add microphone permission flow`
   - Rough time estimate: 2-4 hours

4. [ ] **Create `SpeechToTextService`**
   - Exact files to create or modify: `lib/features/voice/data/speech_to_text_service.dart`, `lib/features/voice/application/voice_controller.dart`
   - What must be implemented: Wrap the STT package behind a clean service with initialize, startListening, stopListening, cancel, partial transcript callback, final transcript callback, and error callback.
   - Success criteria: The rest of the app depends on the service interface, not package-specific APIs, and partial transcripts can be surfaced during listening.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add speech to text service`
   - Rough time estimate: 3-5 hours

5. [ ] **Create `TextToSpeechService`**
   - Exact files to create or modify: `lib/features/voice/data/text_to_speech_service.dart`, `lib/features/voice/application/voice_controller.dart`
   - What must be implemented: Wrap TTS playback behind a service with speak, stop, pause if supported, completion callback, error callback, and basic voice/rate/pitch defaults tuned for natural conversation.
   - Success criteria: Assistant responses can be spoken aloud, playback can be interrupted, and errors do not crash the chat flow.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add text to speech service`
   - Rough time estimate: 3-5 hours

6. [ ] **Wire `VoiceController` into the existing chat pipeline**
   - Exact files to create or modify: `lib/features/voice/application/voice_controller.dart`, `lib/features/chat/application/chat_controller.dart`, `lib/services/chat_api.dart`, `lib/core/providers.dart`
   - What must be implemented: When STT returns a final transcript, send it through the existing `ChatController.sendMessage()` path with streaming enabled. Collect the assistant response text and pass it to TTS when complete.
   - Success criteria: Voice input creates the same conversation messages as typed input, uses the existing `/chat` streaming pipeline, and preserves current conversation behavior.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: connect voice input to chat pipeline`
   - Rough time estimate: 4-6 hours

7. [ ] **Add push-to-talk UI to ChatPage**
   - Exact files to create or modify: `lib/features/chat/presentation/pages/chat_page.dart`, `lib/features/chat/presentation/widgets/chat_input_bar.dart`, `lib/features/voice/presentation/widgets/voice_recorder_sheet.dart`
   - What must be implemented: Add a clean microphone button near the existing input bar. Pressing it opens a voice recorder sheet with state-specific UI for idle, listening, transcribing, thinking, speaking, failed, and permission denied.
   - Success criteria: A user can start and stop a foreground voice turn without typing, see live feedback, and return to normal text input without layout issues.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add push to talk voice UI`
   - Rough time estimate: 4-7 hours

8. [ ] **Support interruption and cancellation**
   - Exact files to create or modify: `lib/features/voice/application/voice_controller.dart`, `lib/features/voice/data/speech_to_text_service.dart`, `lib/features/voice/data/text_to_speech_service.dart`, `lib/features/voice/presentation/widgets/voice_recorder_sheet.dart`
   - What must be implemented: Add cancel/stop controls for listening and speaking. If the user cancels during listening, discard the transcript. If the user cancels during speaking, stop TTS without deleting the assistant message.
   - Success criteria: The user can recover from accidental recordings, stop Rex mid-answer, and start a new voice turn without stale state leaking across turns.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add voice cancellation controls`
   - Rough time estimate: 3-5 hours

9. [ ] **Add tests for voice state transitions**
   - Exact files to create or modify: `test/features/voice/application/voice_controller_test.dart`, `test/features/voice/presentation/voice_recorder_sheet_test.dart`, existing provider test helpers if needed
   - What must be implemented: Unit/widget tests for permission denied, listening to partial transcript, final transcript submission, thinking state, speaking state, TTS completion, STT error, TTS error, and cancellation.
   - Success criteria: Tests cover the main happy path and failure paths without requiring real microphone access or real TTS playback.
   - Verification / test command: `flutter test test/features/voice && flutter analyze && flutter test`
   - Suggested git commit message: `test: cover voice controller states`
   - Rough time estimate: 4-6 hours

10. [ ] **Run full validation and manual foreground voice test**
    - Exact files to create or modify: No code changes expected unless validation exposes bugs
    - What must be implemented: Run full Flutter checks, then manually test a full voice turn on a device or simulator: tap mic, speak, see transcript, send to Rex, receive streamed answer, hear spoken response, interrupt playback, and send another turn.
    - Success criteria: `flutter analyze` and `flutter test` pass, typed chat still works, voice chat works in foreground, and failures produce clear UI instead of silent breakage.
    - Verification / test command: `flutter analyze && flutter test`
    - Suggested git commit message: `test: validate foreground voice mvp`
    - Rough time estimate: 2-4 hours

## Revision History
- 2026-05-12 - Action Plan 2 created from Alignment Plan and updated REX_VISION.md
