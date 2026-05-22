# iOS Background Voice Hard Audit

## Executive Summary

The current iOS native voice path is much better than the old Flutter-owned path, but it is still not a true background conversation engine.

The key failure is a background execution gap:

1. Rex is speaking or listening while the app is minimized.
2. The user speaks in the background.
3. Native capture records and streams the speech.
4. Native endpointing emits `utterance.end`.
5. `RexNativeVoiceBridge` immediately stops `AVAudioEngine`.
6. The app is now backgrounded with no active recording and no active playback yet.
7. Rex waits on WebSocket callbacks, Deepgram finalization, Grok, and Google TTS.
8. iOS can suspend the app during that gap.
9. When the app is reopened, queued callbacks continue and Rex resumes from where it was stuck.

This matches the user report: audio is captured in the background, but Rex does not actually begin or complete the response until the app returns to the foreground.

This is not primarily a microphone permission problem, not a VAD threshold problem, and not a backend crash. It is a native lifecycle ownership problem.

## Current Architecture

The intended active native path is:

```text
iOS AVAudioEngine
-> RexNativeAudioCapture
-> RexNativeVoiceWebSocket
-> FastAPI /voice/stream
-> Deepgram live transcription
-> Chat/Grok stream
-> Google TTS
-> assistant.audio_chunk events
-> RexNativeAudioPlayback
-> return to native capture
```

This is the right direction. The missing piece is keeping the app legitimately alive during the server-processing gap between user speech ending and assistant audio starting.

## Platform Constraints

Apple's audio system requires the app to describe its audio behavior through `AVAudioSession`. Apple's `AVAudioSession` documentation says the default iOS audio session does not allow recording and lock-screen behavior is limited until the session is configured. It also states that background audio playback requires the audio background mode. Source: [Apple AVAudioSession documentation](https://developer.apple.com/documentation/avfaudio/avaudiosession).

Rex already declares:

```text
UIBackgroundModes = audio
```

That is necessary, but not sufficient. Background execution is kept alive by active audio work, not just by the Info.plist flag.

Apple documents `AVAudioSession.Mode.voiceChat` as intended for two-way voice communication. Source: [Apple AVAudioSession mode documentation](https://developer.apple.com/documentation/avfaudio/avaudiosession/mode-swift.struct?changes=latest_ma_3&language=objc).

Apple documents `URLSessionWebSocketTask` as a WebSocket transport with async send/receive callbacks. Source: [Apple URLSessionWebSocketTask documentation](https://developer.apple.com/documentation/foundation/urlsessionwebsockettask).

Apple's background `URLSessionConfiguration` is for HTTP/HTTPS uploads and downloads handled by the system in a separate process. Source: [Apple background URLSessionConfiguration documentation](https://developer.apple.com/documentation/foundation/urlsessionconfiguration/1407496-background).

Implication: a live WebSocket receive loop is not a substitute for an active background audio session. If capture is stopped and playback has not started yet, Rex is depending on ordinary app execution while backgrounded.

## Evidence From Code

### Finding 1: The bridge stops capture exactly when background execution is most fragile

File: `ios/Runner/RexNativeVoiceBridge.swift`

At `utterance.end`, the bridge stops capture before asking the backend to process the turn:

```swift
if event == "utterance.end" {
  audioCapture.stop()
  try ensureTransportConnected()
  voiceWebSocket.endUtterance()
}
```

This is the main gap. In foreground, this is fine. In background, this removes the active audio input before assistant playback begins.

Expected bad timeline:

```text
background app
-> user finishes speaking
-> AVAudioEngine stops
-> no playback yet
-> WebSocket waits for assistant.started / audio_chunk
-> iOS suspends or delays callbacks
-> user reopens app
-> callbacks resume
```

### Finding 2: Playback is native, but it only starts after WebSocket callbacks arrive

File: `ios/Runner/RexNativeVoiceBridge.swift`

Assistant playback starts only after `assistant.audio_chunk` is received:

```swift
if event == "assistant.audio_chunk" {
  enqueueAssistantAudio(payload)
}
```

File: `ios/Runner/RexNativeAudioPlayback.swift`

The native player begins after a chunk is enqueued:

```swift
queue.append(chunk)
playNextIfNeeded()
```

If the app is suspended before `assistant.audio_chunk` is delivered to the native WebSocket callback, native playback never starts in the background.

### Finding 3: The WebSocket uses a default URLSession

File: `ios/Runner/RexNativeVoiceWebSocket.swift`

```swift
private let urlSession = URLSession(configuration: .default)
```

This is normal for foreground and active audio contexts. It is not a guaranteed background transfer mechanism. Apple's background URLSession API is for uploads/downloads, not for keeping an interactive WebSocket receive loop alive while the app has no active audio.

### Finding 4: The native bridge still emits state through Flutter EventChannel

File: `ios/Runner/RexNativeVoiceBridge.swift`

```swift
private func emit(_ payload: [String: Any]) {
  DispatchQueue.main.async { [weak self] in
    self?.eventSink?(payload)
  }
}
```

This is fine for updating UI. It should not be required for the background conversation to continue. The background voice loop must be able to proceed fully inside Swift even if Flutter/Dart is paused.

Right now, the core audio and transport are native, but state visibility and recovery still depend heavily on events flowing back to Flutter.

### Finding 5: `isForeground` is tracked but not used to change policy

File: `ios/Runner/RexNativeVoiceBridge.swift`

The bridge stores foreground state:

```swift
private var isForeground = true
```

and updates it:

```swift
isForeground = payload["isForeground"] as? Bool ?? isForeground
```

But it does not use this to change behavior. The bridge treats foreground and background `utterance.end` the same way.

That is wrong for this feature. In foreground, stopping capture while waiting for the server is safe. In background, the app needs a background-safe handoff strategy.

### Finding 6: Assistant timeout can also pause with the app

File: `ios/Runner/RexNativeVoiceWebSocket.swift`

```swift
queue.asyncAfter(deadline: .now() + 25, execute: workItem)
```

If the process is suspended, this timeout cannot be trusted as a real wall-clock watchdog. It helps foreground failures, but it does not prove background liveness.

### Finding 7: The backend is probably not the blocker

The VPS logs show accepted WebSocket connections, open/close cycles, and no obvious backend traceback in the user reports. The backend also already has the important native-iOS fix: it waits for explicit `utterance.end` instead of Deepgram `speech_final`.

The remaining issue happens after the phone has captured speech and before/while the assistant response starts. That points to iOS client lifecycle, not FastAPI request handling.

## What Is Not The Root Cause

- Not missing `NSMicrophoneUsageDescription`: the microphone works.
- Not missing `UIBackgroundModes/audio`: it is present.
- Not primarily silence detection: foreground endpointing now works.
- Not transcript display: the transcript-chunk issue was separately fixed.
- Not a general backend failure: the same turn continues after reopening.

## The Actual Required Fix

Rex needs a native iOS call-state machine that keeps a valid background audio activity alive across the full turn:

```text
Listening
-> EndingUserTurn
-> WaitingForAssistantStart
-> Speaking
-> RestartingListening
```

The dangerous state is `WaitingForAssistantStart`. Today, that state has no active capture and no active playback.

## Recommended Implementation Plan

### Phase 1: Add Native Background Timeline Telemetry

Goal: prove the exact lifecycle timeline on device.

Modify:

- `ios/Runner/RexNativeVoiceBridge.swift`
- `ios/Runner/RexNativeVoiceWebSocket.swift`
- `ios/Runner/RexNativeAudioCapture.swift`
- `docs/testing/background_voice_checklist.md`

Add native event fields:

- `native_state`
- `is_foreground`
- `is_capturing`
- `is_playing`
- `websocket_connected`
- `audio_session_active`
- `timestamp_ms`

Add events:

- `native.turn.waiting_for_assistant`
- `native.turn.background_audio_gap`
- `native.turn.assistant_started`
- `native.turn.first_audio_chunk`
- `native.turn.playback_started`
- `native.turn.capture_restarted`

Success criteria:

- Real iPhone log clearly shows whether suspension happens after capture stops and before first assistant audio.
- The log can distinguish "backend slow" from "client suspended."

### Phase 2: Keep Background Audio Ownership During The Server Gap

Goal: eliminate the no-audio gap after `utterance.end`.

Modify:

- `ios/Runner/RexNativeAudioCapture.swift`
- `ios/Runner/RexNativeVoiceBridge.swift`

Design:

- Add a capture hold mode.
- On `utterance.end`, do not fully stop `AVAudioEngine` if `isForeground == false`.
- Instead:
  - stop sending microphone chunks to the WebSocket,
  - keep the audio engine/session alive,
  - mark native state as `waitingForAssistant`,
  - send `utterance.end`,
  - stop capture only when `assistant.started` or first `assistant.audio_chunk` arrives.

Important:

- Do not continue uploading background room audio after the user turn ends.
- The engine can remain active to preserve background audio execution, but network upload should be gated off.
- This needs careful App Store wording: Rex is in an active user-started voice call.

Success criteria:

- Minimize Rex while it speaks.
- Speak a follow-up while minimized.
- After silence, Rex starts responding without reopening the app.

### Phase 3: Make Native Swift Own The Voice State Machine

Goal: Flutter becomes UI observer only; Swift owns background call continuity.

Modify:

- `ios/Runner/RexNativeVoiceBridge.swift`
- `ios/Runner/RexNativeVoiceWebSocket.swift`
- `lib/features/voice/application/voice_call_controller.dart`

Design:

- Add a Swift enum:

```swift
enum RexNativeVoiceState {
  case idle
  case listening
  case userSpeaking
  case waitingForAssistant
  case assistantSpeaking
  case restartingListening
  case failed
}
```

- Native bridge transitions internally.
- Flutter receives events when available, but native behavior does not depend on Flutter consuming them.
- Flutter should not be responsible for deciding whether the next background capture should start.

Success criteria:

- Lock screen/background conversation continues even if Flutter EventChannel callbacks are delayed.
- UI catches up correctly when reopened.

### Phase 4: Harden Native WebSocket Background Behavior

Goal: avoid fragile close/reconnect timing in background.

Modify:

- `ios/Runner/RexNativeVoiceWebSocket.swift`
- `backend/app/services/voice_stream_session.py` only if protocol changes are needed.

Options:

1. Prefer one persistent WebSocket per call while the native session is active.
2. If the server or network closes between turns, reconnect before capture restarts, not during the first audio chunk.
3. Add ping/keepalive while waiting for assistant if it does not violate battery/network expectations.

Success criteria:

- VPS logs show stable event order:

```text
session.start
audio.received
utterance.end
assistant.started
assistant.audio_chunk
assistant.done
listening restart
```

- No fatal `Native voice stream closed unexpectedly` for normal turn boundaries.

### Phase 5: Add A Background-Safe Failure Recovery

Goal: if iOS still suspends or network fails, recover without trapping the user.

Modify:

- `ios/Runner/RexNativeVoiceBridge.swift`
- `lib/features/voice/application/voice_call_controller.dart`

Behavior:

- If waiting for assistant in background exceeds a native timeout, keep session active and retry once.
- On foreground resume, if native state is `waitingForAssistant`, resend or verify `utterance.end`.
- If the backend already processed the turn, pull the latest messages/conversation state instead of failing.

Success criteria:

- Reopening the app never leaves Rex permanently stuck in `Thinking`.
- User sees either the completed response or a precise recoverable error.

### Phase 6: Real Device Validation Matrix

Test only on physical devices.

iPhone release build:

- Foreground first turn.
- App minimized while Rex speaks.
- Follow-up spoken while minimized.
- Screen locked while Rex speaks.
- Follow-up spoken while locked.
- 30 second pause before speaking.
- 5 second pause mid-sentence.
- Bluetooth headphones.
- Incoming call interruption.
- Notification interruption.
- Network drop during waiting-for-assistant.

VPS log command:

```bash
sudo journalctl -u rex-backend -f -l
```

iPhone install command:

```bash
flutter run -d 00008150-000C03C83A2B401C --release \
  --dart-define=REX_BACKEND_URL=https://api.rexpilot.com \
  --dart-define=REX_NATIVE_IOS_VOICE_ENABLED=true
```

## Recommended Immediate Code Change

The next implementation should start with Phase 2:

> Do not fully stop native capture on `utterance.end` while backgrounded. Enter a native `waitingForAssistant` hold mode that keeps the audio session alive but stops sending microphone audio.

This directly targets the observed failure. It is smaller and safer than rewriting the whole voice engine, but it moves the system toward the correct architecture.

## Risk Notes

- Keeping audio active in the background must be tied to a visible, user-started call session.
- Do not build stealth always-on listening.
- Avoid pretending WebSocket alone is a background service. It is not the reliable primitive here.
- If App Store distribution becomes a goal, background audio behavior needs clear user-facing justification.

## Final Verdict

Rex is close. The foreground/native call path now works, and background capture can record speech. The missing piece is the handoff from "user finished speaking" to "assistant audio started" while the app is minimized or locked.

The current implementation stops the only active audio engine before assistant playback exists. That is why Rex resumes only after reopening. The fix is to make Swift own a real background-safe turn state machine and keep legitimate audio-session ownership during the waiting-for-assistant gap.
