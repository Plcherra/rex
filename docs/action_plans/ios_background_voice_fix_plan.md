# iOS Background Voice Fix Plan

## Goal

Make Rex continue a real voice conversation while the iPhone app is minimized or the screen is locked.

Target behavior:

```text
User starts Call Rex
-> Rex listens
-> user minimizes or locks screen
-> Rex answers in background
-> user speaks follow-up in background
-> Rex processes and replies without reopening the app
```

This plan follows the findings in `docs/action_plans/ios_background_voice_hard_audit.md`.

## Current Root Cause

The iOS native path captures audio in the background, but it still creates a background execution gap:

```text
User finishes speaking
-> native capture emits utterance.end
-> RexNativeVoiceBridge stops AVAudioEngine
-> no capture is active
-> no playback is active yet
-> app is backgrounded
-> iOS can suspend callbacks before assistant audio arrives
```

When the app is reopened, the suspended callbacks resume. That is why Rex appears stuck and then continues from where it stopped.

## Success Criteria

- [x] Rex can complete voice turns while the app is minimized.
- [x] Rex can complete voice turns while the screen is locked.
- [x] After the user stops speaking in background, Rex starts answering without reopening the app.
- [x] Reopening the app shows the correct current state and transcript, not stale `Thinking`.
- [x] VPS logs show normal `/voice/stream` activity with no backend traceback.
- [x] If iOS rejects a background restart, Rex reports/defers a precise recoverable state instead of silently hanging.

Validated on 2026-05-22 with a physical iPhone release build using `REX_NATIVE_IOS_VOICE_ENABLED=true`.

## Phase 1: Native Background Timeline Telemetry

Purpose: prove exactly where the background turn stalls before changing behavior.

### Files

- `ios/Runner/RexNativeVoiceBridge.swift`
- `ios/Runner/RexNativeVoiceWebSocket.swift`
- `ios/Runner/RexNativeAudioCapture.swift`
- `ios/Runner/RexNativeAudioPlayback.swift`
- `docs/testing/background_voice_checklist.md`

### Steps

- [x] Add a native state enum:

```swift
enum RexNativeVoiceState: String {
  case idle
  case listening
  case userSpeaking
  case waitingForAssistant
  case assistantSpeaking
  case restartingListening
  case failed
}
```

- [x] Emit timeline events with:
  - `native_state`
  - `is_foreground`
  - `is_capturing`
  - `is_playing`
  - `websocket_connected`
  - `timestamp_ms`
  - `reason`

- [x] Add events:
  - `native.turn.waiting_for_assistant`
  - `native.turn.background_audio_gap`
  - `native.turn.assistant_started`
  - `native.turn.first_audio_chunk`
  - `native.turn.playback_started`
  - `native.turn.capture_restarted`

- [x] Document real-device logs in `docs/testing/background_voice_checklist.md`.

### Test Commands

```bash
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

### Device Test

```bash
flutter run -d 00008150-000C03C83A2B401C --release \
  --dart-define=REX_BACKEND_URL=https://api.rexpilot.com \
  --dart-define=REX_NATIVE_IOS_VOICE_ENABLED=true
```

VPS log:

```bash
sudo journalctl -u rex-backend -f -l
```

### Success Criteria

- The iPhone log clearly shows whether the stall happens after `utterance.end`, before `assistant.started`, before first `assistant.audio_chunk`, or during playback.
- The log proves whether the app is entering the no-capture/no-playback gap.

## Phase 2: Add Native Waiting-For-Assistant Hold Mode

Purpose: remove the no-audio background gap.

### Files

- `ios/Runner/RexNativeAudioCapture.swift`
- `ios/Runner/RexNativeVoiceBridge.swift`
- `test/features/voice/application/voice_call_controller_test.dart` if Flutter expectations need updates
- `docs/testing/background_voice_checklist.md`

### Design

When `utterance.end` fires in the background, do not fully stop `AVAudioEngine`.

Instead:

```text
capture continues owning audio session
-> microphone upload is muted/gated
-> bridge sends utterance.end
-> native state becomes waitingForAssistant
-> capture remains held through assistant playback
-> capture resumes from hold after assistant.done/playback drain
```

### Steps

- [x] Add a capture hold mode to `RexNativeAudioCapture`.
- [x] Add a flag like `shouldForwardAudioChunks`.
- [x] On `utterance.end`:
  - foreground: keep current behavior if safe.
  - background: enter hold mode instead of `audioCapture.stop()`.
- [x] In hold mode:
  - keep `AVAudioEngine` alive.
  - stop forwarding audio chunks to `RexNativeVoiceWebSocket`.
  - emit telemetry that capture is holding background audio ownership.
- [x] Through `assistant.started` / `assistant.audio_chunk`:
  - keep capture in hold while assistant audio plays.
  - prevent microphone upload and endpointing during playback.
- [x] After `assistant.done` and playback drain:
  - resume capture from hold when possible.
  - defer restart until foreground if iOS rejects background capture start.
- [x] On error/session end:
  - fully stop capture.

### Acceptance Criteria

- Background app no longer has a period where capture and playback are both inactive.
- Rex starts answering while minimized after the user finishes speaking.
- No extra room audio is uploaded after `utterance.end`.

### Test Commands

```bash
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

## Phase 3: Make Swift Own The Background Voice State Machine

Purpose: make Flutter a UI observer, not the engine that keeps the background call alive.

### Files

- `ios/Runner/RexNativeVoiceBridge.swift`
- `ios/Runner/RexNativeVoiceWebSocket.swift`
- `ios/Runner/RexNativeAudioCapture.swift`
- `ios/Runner/RexNativeAudioPlayback.swift`
- `lib/features/voice/application/voice_call_controller.dart`
- `lib/features/voice/data/native_voice_session_service.dart`

### Steps

- [ ] Store native state in Swift.
- [ ] Centralize transitions in one method:

```swift
private func transition(to next: RexNativeVoiceState, reason: String)
```

- [ ] Make these transitions native-owned:
  - `listening -> userSpeaking`
  - `userSpeaking -> waitingForAssistant`
  - `waitingForAssistant -> assistantSpeaking`
  - `assistantSpeaking -> restartingListening`
  - `restartingListening -> listening`
  - any state -> `failed`

- [ ] Flutter should update UI from events, but not be required for the next native action.
- [ ] On app foreground, Flutter should ask native for current state or receive a state snapshot.

### Acceptance Criteria

- If Flutter/Dart is paused, native iOS can still:
  - finish a user turn,
  - wait for assistant,
  - play assistant audio,
  - restart listening.
- When the app reopens, UI catches up to native state.

### Test Commands

```bash
flutter analyze
flutter test
flutter build ios --debug --no-codesign
```

## Phase 4: Harden WebSocket Turn Boundaries

Purpose: avoid fragile close/reconnect behavior while backgrounded.

### Files

- `ios/Runner/RexNativeVoiceWebSocket.swift`
- `ios/Runner/RexNativeVoiceBridge.swift`
- `backend/app/services/voice_stream_session.py` only if protocol changes are needed
- `tests/test_voice_stream_routes.py`

### Steps

- [ ] Prefer one native WebSocket per active call session if practical.
- [ ] If the backend closes between turns, reconnect before restarting capture.
- [ ] Add explicit native events:
  - `transport.ready_for_next_turn`
  - `transport.reconnecting`
  - `transport.reconnected`
  - `transport.reconnect_failed`
- [ ] Keep normal turn-boundary closes non-fatal.
- [ ] Add tests for native turn-boundary close behavior.

### Acceptance Criteria

VPS logs show clean order:

```text
session.start
audio.received
utterance.end
assistant.started
assistant.audio_chunk
assistant.done
transport.closed reason=turn_complete or session remains open
capture restarted
```

No normal completed turn should show:

```text
Native voice stream closed unexpectedly
```

### Test Commands

```bash
PYTHONPATH=backend python3 -m pytest -q tests/test_voice_stream_routes.py
flutter test test/features/voice/application/voice_call_controller_test.dart
flutter build ios --debug --no-codesign
```

## Phase 5: Native Background Recovery And Resume Reconciliation

Purpose: if iOS still suspends or the network fails, recover cleanly.

### Files

- `ios/Runner/RexNativeVoiceBridge.swift`
- `ios/Runner/RexNativeVoiceWebSocket.swift`
- `lib/features/voice/application/voice_call_controller.dart`
- `backend/app/routes/conversations.py` or existing conversation refresh path if needed

### Steps

- [ ] Add native timeout for `waitingForAssistant`.
- [ ] If timeout fires in background:
  - keep session active,
  - retry `utterance.end` or reconnect once,
  - emit `native.turn.waiting_retry`.
- [ ] On app foreground:
  - request native state snapshot.
  - if state is `waitingForAssistant`, verify whether backend has completed the turn.
  - if messages exist, update UI instead of failing.
- [ ] If recovery fails, show precise message:

```text
Rex heard you in the background, but iOS paused the response before audio started. Tap Try Again.
```

### Acceptance Criteria

- Reopening the app never leaves Rex indefinitely stuck in `Thinking`.
- The UI either shows the completed response or a precise recoverable error.

### Test Commands

```bash
flutter analyze
flutter test
PYTHONPATH=backend python3 -m pytest -q tests
```

## Phase 6: Physical Device Validation

Purpose: prove the feature works on a real iPhone.

### iPhone Release Install

```bash
flutter run -d 00008150-000C03C83A2B401C --release \
  --dart-define=REX_BACKEND_URL=https://api.rexpilot.com \
  --dart-define=REX_NATIVE_IOS_VOICE_ENABLED=true
```

### VPS Deploy/Restart

```bash
cd /opt/rex
git pull
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m pytest -q tests
sudo systemctl restart rex-backend
sudo systemctl status rex-backend --no-pager -l
sudo journalctl -u rex-backend -f -l
```

### Test Matrix

- [x] Foreground first turn.
- [x] Minimize while Rex speaks.
- [x] Speak follow-up while minimized.
- [x] Complete minimized turns without reopening.
- [x] Lock screen while Rex speaks.
- [x] Speak follow-up while locked.
- [x] Complete locked-screen turns.
- [x] Pause mid-sentence after endpointing tuning.
- [x] Wait before speaking after no-speech timeout tuning.
- [ ] Use Bluetooth headphones.
- [ ] Receive notification during listening.
- [ ] Receive call interruption.
- [ ] Drop network during `waitingForAssistant`.
- [x] Reopen app after background cases and verify UI state is correct.

### Pass Criteria

- Rex speaks back in the background without requiring foreground resume.
- The app does not remain stuck in `Thinking`.
- Native logs show no audio ownership gap between user speech ending and assistant playback starting.
- VPS logs show no backend error.

## Implementation Order

Recommended sequence:

1. Phase 1 telemetry.
2. Phase 2 hold mode.
3. Real-device test.
4. Phase 3 native state machine.
5. Phase 4 WebSocket hardening.
6. Phase 5 recovery.
7. Phase 6 validation.

Do not skip Phase 1. Without native timeline telemetry, the next failure will look ambiguous again.

## Suggested Commit Messages

```text
docs: add ios background voice fix plan
feat: add native voice background telemetry
fix: keep ios audio session alive while waiting for assistant
refactor: move ios voice call state machine into native bridge
fix: harden native websocket turn boundaries
fix: recover ios background voice state on resume
test: document ios background voice validation
```
