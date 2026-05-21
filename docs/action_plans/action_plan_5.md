# Action Plan 5 - Background & Locked-Screen Voice Continuation

## Goal
Enable voice conversations to continue naturally when the user minimizes the app, switches to other apps, or locks/turns off the screen -- similar to how Grok or ChatGPT voice mode behaves.

## Why This Matters (Personal Context)
This phase makes Rex truly usable in the founder’s real daily life. The founder wants to talk to Rex while walking with the phone in their pocket, lock the screen, switch apps, or even turn the screen off, and still have the voice flow (listening -> thinking -> speaking) continue without interruption. This is the difference between a toy voice feature and a genuine hands-free co-pilot that works during real-world movement, thinking, and daily routines.

## Key Deliverables
- Research and implement feasible background audio handling on iOS and Android within platform limits
- Configure proper audio session categories and background modes
- Handle interruptions (incoming calls, notifications, headphones, screen lock)
- Ensure the voice flow (listening -> thinking -> speaking) survives app backgrounding and screen off where possible
- Add clear UX feedback when background continuation is limited by the OS
- Document realistic platform constraints

## Estimated Time
1-3 weeks (solo founder pace) depending on platform constraints

## Dependencies
Action Plan 2 (Minimal Voice-First Personal Rex) must be 100% complete.

## Current Status - 2026-05-21
Action Plan 5 is partially complete, not finished. The app has the correct background scaffolding: iOS background audio declarations, audio-session configuration, Android foreground-service declarations, interruption handling, UX fallback states, and app-resume recovery for the active call controller.

Physical iPhone validation found the important remaining failure: Rex can stop hearing the user when the screen locks or the app is backgrounded. The cause is architectural, not just configuration. The active streaming path still captures microphone frames through Flutter/Dart (`record.startStream`) and sends them over a Dart WebSocket. iOS can suspend that path when the app leaves the foreground.

The next part of Action Plan 5 is therefore a native locked-screen voice implementation:

- iOS: native `AVAudioSession` + `AVAudioEngine` capture that owns microphone recording while backgrounded, with a bridge back to Flutter.
- Android: foreground service should own microphone capture, not only display a notification while Flutter owns capture.
- Flutter controller: keep the resume recovery and UI feedback, but treat it as recovery, not proof of continuous locked-screen capture.

## Missing Implementation Layers
The current code has the server contract and Flutter call UX, but true locked-screen voice still needs these layers:

1. **iOS native bridge**
   - Current gap: `rex/voice_background` has an Android handler only. iOS `AppDelegate.swift` does not register a voice background channel.
   - Needed: iOS `MethodChannel` or `EventChannel` for starting/stopping native voice sessions and streaming native status/transcript/audio events back to Flutter when the app is foregrounded again.

2. **iOS native microphone owner**
   - Current gap: active capture uses Flutter `record.startStream`, which can stop when iOS suspends Dart.
   - Needed: native `AVAudioEngine` input tap configured under `AVAudioSessionCategoryPlayAndRecord` + `AVAudioSessionModeVoiceChat`, converting microphone buffers to the backend's expected PCM 16-bit 16 kHz mono stream.

3. **iOS native WebSocket owner**
   - Current gap: `StreamingVoiceApi` uses Dart `WebSocket.connect`, so the network stream is also suspended with Dart.
   - Needed: native `URLSessionWebSocketTask` that speaks the existing `/voice/stream` protocol:
     - send `session.start`
     - send binary PCM chunks
     - send `utterance.end`
     - receive transcript, assistant, and audio events
     - send `user.interrupt` and `session.end`

4. **iOS native playback path**
   - Current gap: assistant audio is played through Flutter `audioplayers`; this may not be reliable when Dart is suspended.
   - Needed: native playback queue using `AVAudioPlayerNode`, `AVAudioEngine`, or another background-safe AVFoundation path for received TTS audio chunks.

5. **iOS background state and interruptions**
   - Current gap: lifecycle recovery exists in Flutter, but route changes, interruptions, and lock-screen behavior are not owned by native voice session code.
   - Needed: native observers for `AVAudioSession.interruptionNotification`, route changes, engine resets, app background/foreground, and audio-session reactivation after interruption.

6. **Android service-owned capture**
   - Current gap: `RexVoiceForegroundService` only shows a foreground notification. Flutter still owns capture.
   - Needed: service-owned microphone capture using `AudioRecord`, with foreground-service lifetime controlling capture and wake behavior.

7. **Android service-owned WebSocket and playback**
   - Current gap: Dart owns `/voice/stream` and playback.
   - Needed: service-owned WebSocket client, binary PCM chunk sender, event parser, and native playback queue. Android likely needs an OkHttp WebSocket dependency or equivalent native networking implementation.

8. **Runtime permissions and OS policy checks**
   - Current gap: manifest declarations exist, but real-device behavior depends on runtime notification/microphone permissions and foreground-service rules.
   - Needed: confirm `POST_NOTIFICATIONS` is requested on Android 13+, confirm microphone permission before service start, and show clear UI if the OS blocks background mic.

9. **Flutter/native state contract**
   - Current gap: Flutter owns `VoiceCallState`; native background voice would have its own independent session state unless bridged carefully.
   - Needed: a small cross-platform contract for session status:
     - idle/listening/thinking/speaking/failed
     - current transcript
     - assistant response
     - conversation id
     - recoverable error
     - whether the native session is still alive after resume
     - backend base URL and active conversation id passed from Flutter into native at session start

10. **Backpressure, reconnect, and cleanup**
    - Current gap: Dart session cleanup works for foreground use, but native lock-screen mode needs explicit recovery rules.
    - Needed: heartbeat/timeouts, network loss handling, audio queue bounds, single active session guard, guaranteed stop on hangup, and no zombie microphone after crashes or route changes.

11. **Device acceptance tests**
    - Current gap: automated tests prove state transitions, not OS background behavior.
    - Needed: physical-device acceptance matrix for iPhone lock screen, app switch, screen off, AirPods/Bluetooth, incoming call, network drop, long session, second utterance after lock, and Android foreground-service parity.

12. **Review `UIBackgroundModes/processing`**
    - Current gap: `processing` is declared, but live voice does not currently use a `BGProcessingTask`.
    - Needed: either remove `processing` if unused or add the required background-task identifiers and implementation. It does not solve live locked-screen voice by itself and may create App Store review confusion.

## Checklist (15 Actionable Steps)

1. [x] **Research platform limits and choose the background voice approach**
   - Exact files to create or modify: `docs/background_voice_constraints.md`, optionally `docs/action_plans/action_plan_5.md`
   - What must be implemented: Document what iOS and Android realistically allow for microphone capture, Deepgram transcription, Google TTS playback, foreground services, lock-screen behavior, and app backgrounding. Decide the MVP strategy for each platform before touching native code.
   - Success criteria: The team has a clear written decision for what Rex will support, what is OS-limited, what requires foreground service/background audio, and what will be deferred.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `docs: define background voice platform constraints`
   - Rough time estimate: 4-8 hours

2. [x] **Add audio session configuration layer**
   - Exact files to create or modify: `lib/features/voice/data/audio_session_service.dart`, `lib/features/voice/application/voice_controller.dart`, `lib/core/providers.dart`
   - What must be implemented: Create a service that configures audio session behavior for recording and speaking, including microphone input, speaker/headphones routing, interruption handling hooks, and active/inactive session transitions.
   - Success criteria: Voice services no longer configure audio behavior ad hoc, and the app has one place to manage audio mode transitions for STT and TTS.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add audio session service`
   - Rough time estimate: 4-6 hours

3. [x] **Configure iOS background audio and permissions**
   - Exact files to create or modify: `ios/Runner/Info.plist`, `ios/Runner.xcodeproj/project.pbxproj`, iOS app capability settings if needed, `docs/background_voice_constraints.md`
   - What must be implemented: Add the required microphone usage description, speech recognition usage description if applicable, and background audio mode configuration. Document exactly which iOS background behaviors are supported and which are limited by Apple policies.
   - Success criteria: iOS builds successfully, permission prompts are clear, audio playback can continue where allowed, and limitations around continuous background listening are explicitly documented.
   - Verification / test command: `flutter analyze && flutter test && flutter build ios --debug --no-codesign`
   - Suggested git commit message: `feat: configure ios background audio`
   - Rough time estimate: 4-8 hours

4. [x] **Configure Android foreground service and audio focus**
   - Exact files to create or modify: `android/app/src/main/AndroidManifest.xml`, Android Kotlin/Java files under `android/app/src/main/`, `lib/features/voice/data/audio_session_service.dart`, `docs/background_voice_constraints.md`
   - What must be implemented: Add required permissions, foreground service setup, audio focus handling, notification channel, and persistent foreground notification for active voice sessions where needed.
   - Success criteria: Android can keep an active voice session alive more reliably during app backgrounding, and the user sees a clear system notification while Rex is using microphone/audio in the background.
   - Verification / test command: `flutter analyze && flutter test && flutter build apk --debug`
   - Suggested git commit message: `feat: configure android background voice service`
   - Rough time estimate: 1-2 days

5. [x] **Add app lifecycle handling to voice state**
   - Exact files to create or modify: `lib/features/voice/application/voice_controller.dart`, `lib/features/voice/domain/voice_state.dart`, `lib/features/voice/data/audio_recording_service.dart`, `lib/features/voice/data/audio_playback_service.dart`
   - What must be implemented: React to app lifecycle events such as resumed, inactive, paused, detached, and hidden. Decide when to continue listening, pause listening, continue speaking, stop speaking, or show an OS limitation state.
   - Success criteria: Voice state transitions are explicit when the app is backgrounded or resumed, and Rex does not silently lose an active voice turn.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: handle voice app lifecycle changes`
   - Rough time estimate: 5-8 hours

6. [x] **Handle audio interruptions and route changes**
   - Exact files to create or modify: `lib/features/voice/data/audio_session_service.dart`, `lib/features/voice/application/voice_controller.dart`, `lib/features/voice/presentation/widgets/voice_recorder_sheet.dart`
   - What must be implemented: Handle incoming calls, notification interruptions, headphones disconnecting, Bluetooth route changes, audio focus loss, and TTS/STT errors caused by interruption. Add recovery states and user-facing messages.
   - Success criteria: Interruptions do not leave Rex stuck in listening, thinking, or speaking state, and the user can resume or restart the voice turn cleanly.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: handle voice audio interruptions`
   - Rough time estimate: 6-10 hours

7. [x] **Add background continuation UX feedback**
   - Exact files to create or modify: `lib/features/voice/presentation/widgets/voice_recorder_sheet.dart`, `lib/features/chat/presentation/pages/chat_page.dart`, `lib/features/voice/domain/voice_state.dart`
   - What must be implemented: Show clear status when background continuation is active, limited, paused by the OS, or requires the app to stay open. Include practical controls to resume, stop, or restart the voice turn.
   - Success criteria: The founder can understand whether Rex is still listening/speaking in background mode, and failures are visible instead of feeling like random silence.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `feat: add background voice status ui`
   - Rough time estimate: 4-7 hours

8. [x] **Add tests for lifecycle, interruption, and fallback states**
   - Exact files to create or modify: `test/features/voice/application/voice_controller_test.dart`, `test/features/voice/presentation/voice_recorder_sheet_test.dart`, existing test fakes for STT/TTS/audio session
   - What must be implemented: Add tests for app pause/resume, audio interruption start/end, route changes, background unsupported state, TTS continuing after backgrounding where allowed, and clean cancellation from background-related failure states.
   - Success criteria: Main background voice state transitions are covered without requiring real microphone, real TTS, or native platform execution in unit tests.
   - Verification / test command: `flutter test test/features/voice && flutter analyze && flutter test`
   - Suggested git commit message: `test: cover background voice state handling`
   - Rough time estimate: 5-8 hours

9. [ ] **Run real-device validation on iOS and Android - in progress**
   - Exact files to create or modify: `docs/background_voice_constraints.md`, optionally `docs/testing/background_voice_checklist.md`
   - What must be implemented: Test real app behavior on physical devices: foreground voice, app switch, screen lock, headphones, incoming call interruption, notification interruption, Bluetooth route change, and long response TTS playback.
   - Current result: iPhone `Pedro Martins` on iOS 26.5 is connected and ready for release-build validation. Android is blocked because no physical Android device is connected. iPhone foreground voice works, but screen lock/app background can stop microphone streaming because capture is still Flutter/Dart-owned. A real iPhone app-switch test found a stuck `Thinking` state after background speech; a watchdog fix now resets stale streams back to `Listening` and needs release-build retest.
   - Validation artifact: `docs/testing/background_voice_checklist.md`
   - Success criteria: Real-device results are documented by platform, known limitations are written down, and major bugs found during device testing are fixed or explicitly deferred.
   - Verification / test command: `flutter analyze && flutter test`
   - Suggested git commit message: `test: document background voice device validation`
   - Rough time estimate: 1-2 days

10. [x] **Finalize graceful degradation and documentation**
    - Exact files to create or modify: `docs/background_voice_constraints.md`, `README.md`, `REX_VISION.md`, `lib/features/voice/presentation/widgets/voice_recorder_sheet.dart`
    - What must be implemented: Document what Rex supports in foreground, background, lock screen, and screen-off states. Add in-app messaging for limitations and make sure unsupported states fail clearly and recoverably.
    - Success criteria: The founder knows exactly what to expect from background voice on each platform, the app communicates limits without technical jargon, and all automated checks pass.
    - Verification / test command: `flutter analyze && flutter test`
    - Suggested git commit message: `docs: finalize background voice limitations`
    - Rough time estimate: 3-5 hours

11. [ ] **Define the native voice session contract**
    - Exact files to create or modify: `lib/features/voice/data/background_voice_service.dart`, `lib/features/voice/domain/voice_call_state.dart`, `ios/Runner/AppDelegate.swift`, `android/app/src/main/kotlin/com/rex/rex/MainActivity.kt`, new platform bridge files if needed.
    - What must be implemented: Define the cross-platform method/event contract before native code grows: start session, stop session, interrupt, mute/unmute, send foreground status to Flutter, receive native transcript/status/audio state, and surface failures.
    - Success criteria: Flutter can start/stop a native voice session through one service interface and receive status events even if capture implementation is still stubbed.
    - Verification / test command: `flutter analyze && flutter test`
    - Suggested git commit message: `feat: define native voice session bridge`
    - Rough time estimate: 0.5-1 day

12. [ ] **Implement iOS native locked-screen voice session**
    - Exact files to create or modify: `ios/Runner/AppDelegate.swift`, new iOS voice capture/session bridge files if needed, `lib/features/voice/data/background_voice_service.dart`, `lib/features/voice/application/voice_call_controller.dart`, `docs/background_voice_constraints.md`
    - What must be implemented: Add native `AVAudioSession`, `AVAudioEngine` capture, PCM conversion, `URLSessionWebSocketTask` protocol handling, native playback queue, interruption handling, and status events back to Flutter.
    - Success criteria: A physical iPhone can start a Rex voice call, lock the screen, speak a second utterance, receive Rex audio, and continue for at least several minutes without reopening the app.
    - Verification / test command: `flutter analyze && flutter test && flutter build ios --no-codesign`, plus physical iPhone lock-screen tests.
    - Suggested git commit message: `feat: add ios locked-screen voice session`
    - Rough time estimate: 3-7 days for iOS MVP.

13. [ ] **Implement Android service-owned voice session**
    - Exact files to create or modify: `android/app/build.gradle.kts`, `android/app/src/main/AndroidManifest.xml`, `android/app/src/main/kotlin/com/rex/rex/RexVoiceForegroundService.kt`, `android/app/src/main/kotlin/com/rex/rex/MainActivity.kt`, new Android voice session classes if needed, `lib/features/voice/data/background_voice_service.dart`
    - What must be implemented: Move capture into the foreground service using `AudioRecord`, stream PCM to `/voice/stream` through a service-owned WebSocket, play assistant audio natively, and keep the visible notification tied to the real active mic session.
    - Success criteria: A physical Android device can start Rex voice mode, background the app, continue speaking, receive Rex audio, and stop cleanly from the app or notification.
    - Verification / test command: `flutter analyze && flutter test && flutter build apk --debug`, plus physical Android foreground-service tests.
    - Suggested git commit message: `feat: add android service-owned voice session`
    - Rough time estimate: 2-5 days after iOS MVP.

14. [ ] **Harden permission, interruption, reconnect, and cleanup behavior**
    - Exact files to create or modify: `lib/features/voice/application/voice_call_controller.dart`, native iOS/Android voice session files, `docs/background_voice_constraints.md`, test files.
    - What must be implemented: Runtime notification/mic permission checks, route-change recovery, incoming-call interruption handling, WebSocket reconnect/fail-fast rules, bounded audio queues, heartbeat/timeouts, and guaranteed microphone release on stop/crash/restart.
    - Success criteria: Rex never leaves the microphone active after the user ends a call, and failures surface as clear UI states instead of silence.
    - Verification / test command: `flutter analyze && flutter test`, plus physical interruption tests.
    - Suggested git commit message: `fix: harden native background voice lifecycle`
    - Rough time estimate: 1-3 days.

15. [ ] **Run final locked-screen acceptance matrix**
    - Exact files to create or modify: `docs/background_voice_constraints.md`, optionally `docs/testing/background_voice_checklist.md`
    - What must be implemented: Record pass/fail results for iPhone and Android: foreground, app switch, screen lock, screen off, second utterance after lock, AirPods/Bluetooth, incoming call, notification interruption, network drop, long session, explicit hangup.
    - Success criteria: Action Plan 5 is only marked complete after physical devices pass or known platform limits are documented with clear fallback behavior.
    - Verification / test command: `flutter analyze && flutter test`
    - Suggested git commit message: `test: validate locked-screen voice on devices`
    - Rough time estimate: 1-2 days.

## Revision History
- 2026-05-21 - Added fix for iPhone app-switch/background stuck-thinking bug; release-build retest required.
- 2026-05-21 - Rescanned implementation and split native locked-screen voice into bridge, iOS, Android, hardening, and device acceptance layers.
- 2026-05-21 - Real-device scan found Flutter-owned streaming does not reliably survive iPhone lock/background. Added native locked-screen capture as the remaining Action Plan 5 work.
- 2026-05-12 - Action Plan 5 created from Alignment Plan and updated REX_VISION.md
- 2026-05-16 - Updated for production cloud voice: Deepgram transcription, Grok reasoning, Google TTS playback, and local STT/TTS only as fallback/dev tooling.
