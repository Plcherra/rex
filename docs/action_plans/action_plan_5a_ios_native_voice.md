# Action Plan 5A - Native iOS Locked-Screen Voice Session

## Goal
Move Rex's iPhone active voice call from a Flutter/Dart-owned microphone and WebSocket pipeline to a native iOS voice session that can keep working when the app is minimized, switched away, or the screen is locked.

This is the iOS-specific continuation of Action Plan 5. The current Flutter recovery layer is useful and should stay, but it is not enough for continuous locked-screen voice because iOS can pause Dart timers, microphone stream callbacks, and Dart WebSocket work after the app leaves the foreground.

## Current Implementation Status - 2026-05-21
Phase 1 is implemented as a native bridge contract stub. The app now has:

- Dart `NativeVoiceSessionService` abstraction.
- Flutter `MethodChannel` named `rex/native_voice`.
- Flutter `EventChannel` named `rex/native_voice_events`.
- iOS `RexNativeVoiceBridge` registered from `AppDelegate`.
- Stub native responses for start, stop, interrupt, mute, and foreground-state changes.
- Unit coverage for Dart channel payloads and missing-plugin fallback.

This does not capture microphone audio natively yet. Phase 2 should replace the stub with `AVAudioSession` and `AVAudioEngine` ownership.

Phase 2 is implemented for native audio-session ownership:

- iOS `RexNativeAudioSession` configures `.playAndRecord` and `.voiceChat`.
- The native bridge activates the iOS audio session on `startSession`.
- The native bridge deactivates the iOS audio session on `stopSession`.
- Interruption, route-change, and media-services events are forwarded through `rex/native_voice_events`.
- `UIBackgroundModes/processing` is removed; `audio` remains.

This still does not capture microphone audio natively. Phase 3 should add `AVAudioEngine` capture.

Phase 3 is implemented for native capture foundation:

- iOS `RexNativeAudioCapture` owns `AVAudioEngine` and installs an input tap.
- iOS `RexPCMConverter` converts capture buffers to PCM16, 16 kHz, mono.
- Native endpoint detection emits `speech.started`, `speech.ended`, and `utterance.end`.
- Native capture starts after `AVAudioSession` activation and stops on hangup, interrupt, deinit, or iOS interruption begin.
- The bridge emits capture telemetry (`capture.started`, `audio.chunk`, `audio.captured`, `capture.stopped`) for device validation.

This still does not send audio to the VPS natively. Phase 4 should connect native PCM chunks to `/voice/stream` with `URLSessionWebSocketTask`.

Phase 4 is implemented for native WebSocket transport:

- iOS `RexNativeVoiceWebSocket` uses `URLSessionWebSocketTask`.
- `backendBaseUrl` is converted to `/voice/stream` using `ws`/`wss`.
- Native iOS sends `session.start`, binary PCM chunks, `utterance.end`, `user.interrupt`, and `session.end`.
- Backend text events are forwarded to Flutter through `rex/native_voice_events`.
- The bridge stops native capture when the backend reaches `transcript.final`, `assistant.started`, or `error`.
- Transport timeouts emit recoverable `error` events for missing `session.started` and missing assistant response after `utterance.end`.

This still does not play assistant audio natively or loop back to native listening after playback. Phase 5 should handle native `assistant.audio_chunk` playback.

Phase 5 is implemented for native assistant playback:

- iOS `RexNativeAudioPlayback` queues backend `assistant.audio_chunk` payloads and plays supported MP3-style audio through `AVAudioPlayer`.
- The bridge stops native capture while Rex is speaking.
- Native playback emits `playback.queued`, `speaking.started`, `speaking.ended`, and `playback.error` events.
- Hangup, interrupt, and iOS audio interruption stop playback and clear any pending return-to-listening state.
- After `assistant.done` and playback drain, the bridge restarts native capture and emits `listening`.

Phase 6 is implemented for Flutter controller integration:

- `VoiceCallController` can prefer native iOS voice when `REX_NATIVE_IOS_VOICE_ENABLED=true` and the target platform is iOS.
- Native events from `rex/native_voice_events` now map into the existing call UI state for listening, thinking, speaking, transcript, assistant text, errors, and backend message updates.
- Mute, interrupt, app foreground/background changes, hangup, failure, and reset route to the native session while native mode is active.
- Dart streaming and local capture are skipped while the native iOS session owns the active call.
- Dart streaming remains the fallback when native iOS voice is disabled or native session startup fails.

Phase 7 should validate the native path on a physical iPhone release build.

## Current Evidence
Real iPhone testing on 2026-05-21 showed:

- Foreground streaming voice works.
- When the app is minimized, Rex can sometimes finish one background turn.
- The `/voice/stream` WebSocket opens and closes cleanly on the VPS; the backend is not crashing.
- Flutter-owned capture can fail when trying to restart the next microphone stream in the background.
- The app now recovers on foreground resume, but it does not continuously own microphone + WebSocket + playback while locked.

## Platform Decision
iOS does not provide an Android-style long-running background service. The correct iOS approach is:

- `AVAudioSession` configured for voice recording and playback.
- `UIBackgroundModes` containing `audio`.
- `AVAudioEngine` native microphone capture with an input tap.
- `URLSessionWebSocketTask` native connection to the existing `/voice/stream` backend.
- Native playback for assistant audio chunks.
- Flutter used only for UI, commands, and state display.

Apple documentation references:

- `AVAudioSession`: https://developer.apple.com/documentation/avfaudio/avaudiosession
- `AVAudioSession.Category.record`: https://developer.apple.com/documentation/avfaudio/avaudiosession/category-swift.struct/record
- `AVAudioEngine`: https://developer.apple.com/documentation/avfaudio/avaudioengine/
- `AVAudioNode.installTap`: https://developer.apple.com/documentation/avfaudio/avaudionode/installtap%28onbus%3Abuffersize%3Aformat%3Ablock%3A%29
- `URLSessionWebSocketTask`: https://developer.apple.com/documentation/foundation/urlsessionwebsockettask

## Existing Repo Context
Relevant current files:

- `ios/Runner/AppDelegate.swift`
- `ios/Runner/Info.plist`
- `ios/Runner.xcodeproj/project.pbxproj`
- `lib/features/voice/application/voice_call_controller.dart`
- `lib/features/voice/data/background_voice_service.dart`
- `lib/features/voice/data/streaming_voice_api.dart`
- `lib/features/voice/data/streaming_audio_capture_service.dart`
- `lib/features/voice/domain/voice_call_state.dart`
- `test/features/voice/application/voice_call_controller_test.dart`
- `docs/background_voice_constraints.md`
- `docs/testing/background_voice_checklist.md`

Current iOS `Info.plist` already contains `UIBackgroundModes` with `audio`, but also contains `processing`. If no `BGProcessingTask` is used, remove or justify `processing` during this plan.

## Backend Contract To Preserve
Do not redesign the backend for the iOS MVP. Native iOS must speak the same `/voice/stream` protocol currently used by `StreamingVoiceApi`.

Client to backend:

- Text JSON: `{"event":"session.start","conversation_id":"...","input_mime_type":"audio/linear16","sample_rate":16000}`
- Binary audio: PCM 16-bit mono 16 kHz chunks.
- Text JSON: `{"event":"utterance.end"}`
- Text JSON: `{"event":"user.interrupt"}`
- Text JSON: `{"event":"session.end"}`

Backend to client:

- `session.started`
- `audio.received`
- `transcript.partial`
- `transcript.final`
- `assistant.started`
- `assistant.token`
- `assistant.audio_chunk`
- `messages.updated`
- `assistant.done`
- `session.interrupted`
- `session.ended`
- `error`

## Target Architecture

```text
Flutter VoiceCallController
  -> MethodChannel commands: start / stop / interrupt / mute
  <- EventChannel events: listening / transcript / thinking / token / audio / done / error

iOS RexNativeVoiceSession
  -> AVAudioSession owns voice audio mode
  -> AVAudioEngine input tap captures microphone
  -> PCM converter outputs 16 kHz mono Int16
  -> URLSessionWebSocketTask sends audio + turn events
  <- WebSocket receives transcript/assistant/audio events
  -> Native audio playback queue plays assistant audio
```

Flutter should remain the source of visible UI state, but native iOS should be the source of truth for the active audio session while the phone is locked or backgrounded.

## Phase 1 - Define Native Bridge Contract

### Files To Create Or Modify
- Create `ios/Runner/RexNativeVoiceBridge.swift`
- Create `ios/Runner/RexNativeVoiceEventSink.swift` if needed
- Modify `ios/Runner/AppDelegate.swift`
- Modify `lib/features/voice/data/background_voice_service.dart`
- Create or modify tests under `test/features/voice/application/voice_call_controller_test.dart`

### Implementation
- Add a `MethodChannel` named `rex/native_voice`.
- Add an `EventChannel` named `rex/native_voice_events`.
- Define commands:
  - `startSession`
  - `stopSession`
  - `interrupt`
  - `setMuted`
  - `setForegroundState`
- `startSession` payload:
  - `backendBaseUrl`
  - `conversationId`
  - `sampleRate`
  - `inputMimeType`
- Define native event payloads:
  - `session.started`
  - `listening`
  - `speech.started`
  - `speech.ended`
  - `transcript.partial`
  - `transcript.final`
  - `assistant.started`
  - `assistant.token`
  - `assistant.audio_chunk`
  - `assistant.done`
  - `session.ended`
  - `error`
- Keep the existing `rex/voice_background` channel until replacement is stable.

### Success Criteria
- Flutter can call native `startSession` and receive a stub `session.started` event.
- Flutter can call `stopSession`.
- Missing plugin behavior still works on desktop/tests.
- No real microphone work yet.

### Verification
```sh
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

## Phase 2 - Implement Native Audio Session Ownership

### Files To Create Or Modify
- Create `ios/Runner/RexNativeAudioSession.swift`
- Modify `ios/Runner/RexNativeVoiceBridge.swift`
- Modify `ios/Runner/Info.plist`
- Update `docs/background_voice_constraints.md`

### Implementation
- Configure `AVAudioSession.sharedInstance()` with:
  - category: `.playAndRecord`
  - mode: `.voiceChat`
  - options: `.defaultToSpeaker`, `.allowBluetooth`, `.allowBluetoothA2DP` if appropriate
- Activate the audio session only when the native call starts.
- Deactivate it when the call ends.
- Register observers for:
  - `AVAudioSession.interruptionNotification`
  - `AVAudioSession.routeChangeNotification`
  - media services reset/lost notifications if needed
- Remove `UIBackgroundModes/processing` unless this plan adds a real background processing task.

### Success Criteria
- Native code can activate/deactivate iOS voice audio cleanly.
- Incoming audio interruptions produce native events back to Flutter.
- Mic indicator turns on only during an active Rex call and turns off on hangup.

### Verification
```sh
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

Physical test:
- Start call.
- Hang up.
- Confirm iPhone mic indicator turns off.
- Trigger interruption if practical.

## Phase 3 - Implement Native Microphone Capture

### Files To Create Or Modify
- Create `ios/Runner/RexNativeAudioCapture.swift`
- Create `ios/Runner/RexPCMConverter.swift`
- Modify `ios/Runner/RexNativeVoiceBridge.swift`
- Add iOS unit-testable helper code where practical

### Implementation
- Use `AVAudioEngine`.
- Use `engine.inputNode.installTap(onBus:bufferSize:format:block:)`.
- Convert captured buffers to PCM 16-bit, 16 kHz, mono.
- Keep tap work off the main thread.
- Add lightweight native endpoint detection:
  - detect speech start from amplitude.
  - detect speech end from sustained silence.
  - send `utterance.end` immediately when endpointing fires.
- Emit `speech.started`, `speech.ended`, and transcript/status events to Flutter.

### Success Criteria
- Native iOS can capture microphone frames without using Flutter `record.startStream`.
- Native capture can run while app is minimized at least long enough to detect speech and send audio.
- Capture stops cleanly on hangup, interruption, and error.

### Verification
```sh
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

Physical test:
- Start call.
- Speak in foreground.
- Minimize app while listening.
- Confirm native capture still emits audio/status events.

## Phase 4 - Implement Native WebSocket Transport

### Files To Create Or Modify
- Create `ios/Runner/RexNativeVoiceWebSocket.swift`
- Modify `ios/Runner/RexNativeVoiceBridge.swift`
- Modify `docs/cloud_voice_contract.md` if needed
- Update `docs/testing/background_voice_checklist.md`

### Implementation
- Use `URLSessionWebSocketTask`.
- Convert `https://api.rexpilot.com` to `wss://api.rexpilot.com/voice/stream`.
- Send `session.start` when the socket opens.
- Send binary PCM chunks from native capture.
- Send `utterance.end` immediately when native endpointing fires.
- Receive backend events continuously:
  - forward transcript/status events to Flutter.
  - route `assistant.audio_chunk` to native playback.
  - forward message updates and final assistant text to Flutter.
- Add timeout/error handling:
  - connect timeout.
  - no assistant event after `utterance.end`.
  - backend `error` event.
  - WebSocket closed while active.

### Success Criteria
- Native iOS can complete one foreground voice turn through the existing VPS `/voice/stream`.
- Backend logs show normal WebSocket open/close without errors.
- Flutter Dart `StreamingVoiceApi` is not used for the native iOS path.

### Verification
```sh
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

VPS log command:
```sh
sudo journalctl -u rex-backend -f -l
```

## Phase 5 - Implement Native Assistant Audio Playback

### Files To Create Or Modify
- Create `ios/Runner/RexNativeAudioPlayback.swift`
- Modify `ios/Runner/RexNativeVoiceWebSocket.swift`
- Modify `ios/Runner/RexNativeVoiceBridge.swift`

### Implementation
- Decode backend `assistant.audio_chunk` payloads.
- Play audio natively while the iOS audio session remains active.
- Queue chunks in order.
- Emit playback state to Flutter:
  - `speaking.started`
  - `speaking.ended`
  - `playback.error`
- Return to native listening after playback drains if the call is still active.

### Success Criteria
- Rex can speak while the app is minimized or locked.
- After speaking, native iOS restarts listening without depending on Dart.
- Hangup stops playback immediately.

### Verification
```sh
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

Physical test:
- Ask for a long answer.
- Lock screen during playback.
- Confirm playback continues or fails with a clear recoverable event.

## Phase 6 - Integrate Native iOS Session Into Flutter VoiceCallController

Status: implemented on 2026-05-21. Physical iPhone validation is still required in Phase 7.

### Files To Create Or Modify
- Modify `lib/features/voice/application/voice_call_controller.dart`
- Modify `lib/features/voice/data/background_voice_service.dart`
- Possibly create `lib/features/voice/data/native_voice_session_service.dart`
- Modify `lib/features/voice/domain/voice_call_state.dart`
- Modify `test/features/voice/application/voice_call_controller_test.dart`

### Implementation
- Add a provider/flag for native iOS voice mode.
- On iOS release/device builds, prefer native voice session when enabled.
- Keep Dart streaming as fallback.
- Map native events into existing `VoiceCallState`.
- Keep current watchdog/recovery logic for fallback mode.
- Ensure only one active voice owner exists:
  - either native iOS session
  - or Dart streaming session
  - never both

### Success Criteria
- Existing voice UI works unchanged.
- The call page displays native session status.
- User can mute, interrupt, retry, and hang up.
- Foreground behavior remains at least as good as current Dart streaming.

### Verification
```sh
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

## Phase 7 - Physical iPhone Acceptance Matrix

### Files To Create Or Modify
- Modify `docs/testing/background_voice_checklist.md`
- Modify `docs/background_voice_constraints.md`

### Required Tests
- Foreground voice turn.
- App switch while listening.
- App switch while Rex is thinking.
- App switch during TTS playback.
- Screen lock while listening.
- Screen off after Rex speaks.
- Second user utterance while locked.
- Long response TTS playback.
- AirPods or Bluetooth connected before call.
- Bluetooth route change mid-turn.
- Incoming call interruption.
- Notification interruption.
- Network drop.
- Explicit hangup.
- 3-5 minute multi-turn session.

### Success Criteria
- No fatal `Issue` screen for normal app switch or lock-screen flow.
- No zombie microphone after hangup or crash recovery.
- Rex can complete at least three back-to-back turns while minimized or locked.
- Known OS limitations are documented instead of hidden.

### Verification
```sh
flutter analyze
flutter test
flutter run -d 00008150-000C03C83A2B401C --release \
  --dart-define=REX_BACKEND_URL=https://api.rexpilot.com \
  --dart-define=REX_CLOUD_VOICE_ENABLED=true \
  --dart-define=REX_STREAMING_VOICE_ENABLED=true
```

## Risk Register

### App Store Review Risk
Background audio/recording must be user-visible and justified. Rex should show a clear active call UI and should not behave like hidden always-on listening.

### Battery Risk
Continuous voice capture, WebSocket, STT, TTS, and playback can drain battery. Add clear hangup and timeout behavior.

### Privacy Risk
Mic must stop reliably on hangup, interruption, and app termination. The UI should clearly show when Rex is listening.

### Complexity Risk
Do not build iOS and Android native ownership at the same time. Finish iOS first because that is the active test device and the current failure source.

### Backend Contract Risk
Do not fork the voice protocol unless required. Native iOS should use the current `/voice/stream` contract to avoid backend churn.

## Suggested Commit Sequence

1. `docs: plan native ios locked-screen voice`
2. `feat: add ios native voice bridge`
3. `feat: configure native ios voice audio session`
4. `feat: capture ios microphone natively`
5. `feat: stream ios native voice websocket`
6. `feat: play ios voice responses natively`
7. `feat: wire native ios voice into call controller`
8. `test: validate ios locked-screen voice`

## Definition Of Done
Action Plan 5A is complete only when:

- Native iOS owns microphone capture during an active Rex call.
- Native iOS owns `/voice/stream` while minimized/locked.
- Native iOS owns assistant audio playback while minimized/locked.
- Flutter reflects native state without owning the background pipeline.
- A physical iPhone can complete multiple voice turns with the screen locked.
- Interruptions, hangup, and network failures recover cleanly.
- `flutter analyze`, `flutter test`, and `flutter build ios --debug --no-codesign` pass.
