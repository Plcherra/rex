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

## Checklist (10 Actionable Steps)

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

9. [ ] **Run real-device validation on iOS and Android**
   - Exact files to create or modify: `docs/background_voice_constraints.md`, optionally `docs/testing/background_voice_checklist.md`
   - What must be implemented: Test real app behavior on physical devices: foreground voice, app switch, screen lock, headphones, incoming call interruption, notification interruption, Bluetooth route change, and long response TTS playback.
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

## Revision History
- 2026-05-12 - Action Plan 5 created from Alignment Plan and updated REX_VISION.md
- 2026-05-16 - Updated for production cloud voice: Deepgram transcription, Grok reasoning, Google TTS playback, and local STT/TTS only as fallback/dev tooling.
