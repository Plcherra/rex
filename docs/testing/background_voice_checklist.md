# Background Voice Device Validation Checklist

## Purpose
Track real-device behavior for Action Plan 5 before marking background or locked-screen voice as complete.

Automated tests can validate controller state transitions, but they cannot prove OS behavior for microphone capture, background execution, Bluetooth routing, calls, or lock-screen suspension. This checklist is the source of truth for physical-device results.

## Device Inventory - 2026-05-21

| Platform | Device | OS | Device id | Status |
| --- | --- | --- | --- | --- |
| iOS | Pedro Martins | iOS 26.5 23F77 | `00008150-000C03C83A2B401C` | Available for validation |
| Android | Not connected | Unknown | Unknown | Blocked until a physical Android device is connected |

Device scan command:

```sh
flutter devices
```

iPhone release install command:

```sh
flutter run -d 00008150-000C03C83A2B401C --release --dart-define=REX_BACKEND_URL=https://api.rexpilot.com
```

## Current Known Result

Foreground iPhone voice works well enough to begin physical validation. Screen lock or app background can still stop microphone streaming because the active capture path is Flutter/Dart-owned:

```text
record.startStream -> Dart WebSocket -> backend /voice/stream
```

The app now attempts resume recovery when returning to foreground. That is useful, but it is not proof of continuous locked-screen voice. Action Plan 5A has native iOS audio-session, microphone capture, WebSocket transport, native assistant playback, and Flutter controller integration in place behind `REX_NATIVE_IOS_VOICE_ENABLED=true`. Android still requires service-owned microphone/WebSocket/playback.

## Result Values

Use these values in the tables below:

- `pass`: Works repeatedly on real device.
- `fail`: Reproduced failure.
- `blocked`: Cannot test because setup/device/backend is unavailable.
- `deferred`: Known limitation accepted for a later native implementation.
- `pending`: Not tested yet.

## iOS Validation Matrix

| Case | Expected behavior | Result | Notes |
| --- | --- | --- | --- |
| Foreground voice turn | User starts Rex voice, speaks, gets response, Rex returns to listening. | pending | Test on release build. |
| App switch while listening | User switches away and returns; Rex recovers without silent stuck state. | fail -> fixed in code | 2026-05-21: iPhone completed one minimized follow-up turn, then failed trying to restart the next mic stream in background. Recorder restart failure is now recoverable and waits for foreground resume. Retest on release build. |
| App switch while Rex is thinking | Session does not crash; returning to app shows current state or clear failure. | fail -> fixed in code | 2026-05-21: iPhone captured the background speech but returned stuck on `Thinking` for 2-5 minutes. Added a thinking watchdog and immediate `utterance.end` send on speech endpoint. Retest on release build. |
| App switch during TTS playback | Audio either continues or fails clearly; returning to app is recoverable. | pending | Playback is still Flutter-owned. |
| Screen lock while listening | Rex continues hearing a second utterance while locked. | fail -> partial fix in code | 2026-05-21: iPhone can buffer/capture locked-screen speech, but silence endpointing can pause until unlock. Resume now submits a buffered transcript immediately instead of restarting the stream. Retest required. Native iOS session still required for true locked-screen behavior. |
| Screen off after Rex speaks | Rex hears the next user utterance without reopening the app. | fail | Known limitation until native iOS capture/WebSocket exists. |
| Long response TTS playback | Long assistant answer plays without cutting off or corrupting state. | pending | Include at least 60 seconds of TTS. |
| AirPods or Bluetooth connected before call | Mic route and speaker route are correct. | pending | Note exact headset model. |
| Bluetooth route change mid-turn | Disconnect/connect headset during listening and playback. | pending | Should recover or fail clearly. |
| Incoming call interruption | Call interruption pauses/stops Rex cleanly and releases mic. | pending | Verify no zombie mic after interruption. |
| Notification interruption | Notification does not permanently break the voice session. | pending | Test while listening and speaking. |
| Network drop | Rex surfaces a clear error and can start a new session after network returns. | pending | Toggle Wi-Fi/cellular if safe. |
| Explicit hangup | Stop button releases mic/playback and backend session. | pending | Verify mic indicator turns off. |
| 3-5 minute session | Multiple turns continue without memory leak, stale state, or audio queue buildup. | pending | Foreground test first. |

## Native iOS Transport Validation

Use this once the native bridge is enabled from Flutter:

```sh
sudo journalctl -u rex-backend -f -l
flutter run -d 00008150-000C03C83A2B401C --release \
  --dart-define=REX_BACKEND_URL=https://api.rexpilot.com \
  --dart-define=REX_NATIVE_IOS_VOICE_ENABLED=true
```

Expected native event sequence for one foreground turn:

```text
audio.session.activated
transport.connecting
session.started
capture.started
speech.started
audio.chunk / audio.captured
speech.ended
utterance.end
transport.utterance_end_sent
transcript.final
assistant.started
assistant.token
assistant.audio_chunk
playback.queued
speaking.started
assistant.done
speaking.ended
listening
```

Known Phase 6 limitation: the native iOS path is integrated behind a build flag and now needs physical iPhone release validation before it should be treated as complete.

## Android Validation Matrix

| Case | Expected behavior | Result | Notes |
| --- | --- | --- | --- |
| Foreground voice turn | User starts Rex voice, speaks, gets response, Rex returns to listening. | blocked | Physical Android device not connected. |
| App switch while listening | Foreground service keeps session visible and recoverable. | blocked | Requires Android device. |
| Screen lock while listening | Rex continues hearing a second utterance while locked. | blocked | Current service does not own microphone capture. |
| Screen off after Rex speaks | Rex hears the next user utterance without reopening app. | blocked | Requires service-owned capture/WebSocket. |
| Long response TTS playback | Long assistant answer plays without cutting off or corrupting state. | blocked | Requires Android device. |
| Bluetooth route change mid-turn | Disconnect/connect headset during listening and playback. | blocked | Requires Android device. |
| Incoming call interruption | Call interruption pauses/stops Rex cleanly and releases mic. | blocked | Requires Android device. |
| Notification interruption | Notification does not permanently break the voice session. | blocked | Requires Android device. |
| Network drop | Rex surfaces a clear error and can start a new session after network returns. | blocked | Requires Android device. |
| Explicit hangup | Stop button or notification stop releases mic/playback/backend session. | blocked | Requires Android device. |
| 3-5 minute session | Multiple turns continue without stale state or zombie service. | blocked | Requires Android device. |

## Bug Capture Format

For each failure, record:

```text
Date/time:
Platform/device/OS:
App build:
Git commit:
Backend URL:
Test case:
Steps:
Expected:
Actual:
Logs:
Decision: fix now / defer / platform limitation
```

## Step 9 Acceptance Criteria

Action Plan 5 step 9 is complete only when:

- iOS foreground, app switch, interruption, Bluetooth, long playback, and explicit hangup cases are tested and recorded.
- Android foreground-service cases are tested on a real Android device or explicitly blocked with a device/setup reason.
- Locked-screen limitations are documented as `fail` or `deferred` until native capture is implemented.
- Any major crash, zombie microphone, unrecoverable state, or backend session leak is fixed before moving forward.
- `flutter analyze && flutter test` passes after any fixes.

## Findings

### 2026-05-21 - iPhone background thinking deadlock

Result: `fail -> fixed in code`

Observed behavior:

- Rex was speaking or processing a response.
- The app was minimized and another app was opened.
- The user continued speaking in the background.
- Rex captured the speech, but did not reply.
- Returning to Rex showed the call stuck in `Thinking` for several minutes.

Likely cause:

- The Flutter-owned streaming session can enter `thinking` after ending an utterance, then miss or stall the assistant response events while the app is backgrounded.
- The previous resume recovery only restarted capture when the phase was already `listening`, so a `thinking` state had no fail-safe.

Fix:

- Added a thinking watchdog in `VoiceCallController`.
- If Rex remains in `thinking` too long, the controller interrupts and closes the stale stream, cancels playback/capture, restarts background/audio-session scaffolding, returns to `listening`, and shows a recoverable message.

Retest required:

- Repeat the same iPhone background/app-switch scenario on a release build.
- Confirm Rex no longer stays stuck indefinitely.
- Confirm it either responds normally or resets to `Listening` with the visible recovery message.

### 2026-05-21 - App switch delayed the backend turn boundary

Result: `fail -> fixed in code`

Observed behavior:

- Rex kept the iOS microphone indicator active after the app was minimized.
- After the user stopped speaking, the mic indicator stopped after a short delay.
- Returning to Rex showed the captured transcript, but the assistant response did not start or stayed stuck in `Thinking`.

Likely cause:

- The mobile client changed the UI to `Thinking` inside the speech-ended callback.
- The actual WebSocket `utterance.end` event was sent only after `streamUtterance()` returned.
- On iOS, the app can be minimized or partially suspended between those two steps, leaving the VPS without the turn boundary it needs to start transcription finalization and the assistant response.

Fix:

- `VoiceCallController` now sends `utterance.end` immediately when `onSpeechEnded` fires.
- The later capture-completion path uses the same guarded sender, so the event is not duplicated.
- A regression test verifies that `utterance.end` is sent even while the capture future remains pending.

Retest required:

- Start a release call on iPhone.
- Speak in Rex, minimize the app while still talking, then stop speaking.
- Wait 5-10 seconds, reopen Rex, and verify the assistant has either started responding or the watchdog resets cleanly.
- Watch VPS logs for `/voice/stream` errors if the app still reaches `Thinking` without a reply.

### 2026-05-21 - Background response completed, next mic restart failed

Result: `fail -> fixed in code`

Observed behavior:

- Rex answered while the app was minimized.
- After that answer, the app tried to continue the call and listen for the next user reply.
- The phone returned to Rex in an `Issue` state with `Could not stream voice audio.`
- VPS logs showed WebSocket sessions opening and closing, with no backend crash.

Likely cause:

- The response pipeline could complete in the background.
- The next turn failed when Flutter tried to start a fresh microphone stream while iOS still had the app backgrounded.
- The previous controller path treated any streaming capture start exception as a fatal call failure.

Fix:

- If streaming capture fails while the app is not in the foreground, the controller now keeps the call active in `Listening` instead of moving to `Failed`.
- It closes the stale stream and shows a recoverable message.
- On app resume, the existing resume path restarts the listening stream and clears the recovery message.

Retest required:

- Start a release call.
- Speak, let Rex answer, minimize during the answer, and speak a follow-up.
- If Rex answers in background, leave the app minimized until it tries to listen again.
- Reopen Rex and confirm it is not in the fatal `Issue` screen.
- Confirm it either kept listening or resumed listening cleanly after foregrounding.

### 2026-05-21 - iPhone locked-screen utterance waits until unlock

Result: `fail -> partial fix in code`

Observed behavior:

- Rex continued capturing the user's words while the screen was locked.
- The transcript appeared after unlocking.
- Rex stayed in `Listening` while locked instead of moving into `Thinking`.
- After unlock, Rex could still fall into the stuck-thinking recovery path.

Likely cause:

- Audio/transcript data can be buffered while locked, but Dart-side silence detection and lifecycle work can be delayed until iOS resumes the app.
- The previous resume handler treated a `listening` state as a reason to cancel/restart the stream, even if a transcript had already been captured.

Fix:

- On app resume, if streaming voice is active, Rex is still `Listening`, and there is a buffered transcript, the controller now cancels capture and sends `utterance.end` to the active stream.
- This makes Rex submit the locked-screen utterance immediately after unlock instead of waiting for a silence timer that was paused.

Remaining limitation:

- This is still a foreground-resume recovery. It does not make Rex process the utterance while the screen remains locked. Native iOS voice ownership is still required for that.

### 2026-05-21 - Native iOS turn completed, then stream closed

Result: `fail -> fixed in code`

Observed behavior:

- Native iOS voice captured and completed one background turn.
- The VPS logs showed `/voice/stream` opening and then closing without a backend crash.
- Rex returned to the app in an `Issue` state with `Native voice stream closed unexpectedly.`

Likely cause:

- The backend can close the WebSocket at the end of a completed assistant turn.
- The native iOS transport treated that normal turn-boundary close as a fatal error.
- The bridge restarted microphone capture for the next turn without guaranteeing a fresh WebSocket was ready.

Fix:

- The native WebSocket now marks closes after `assistant.done` or `session.ended` as `transport.closed` with `reason: turn_complete`, not as an error.
- The native bridge stores the current voice config and reconnects the transport before restarting capture or sending the next audio chunk.
- Stale WebSocket callbacks are ignored when a new task has already replaced the old one.

Retest required:

- Start a release call with native iOS voice enabled.
- Speak in Rex, minimize the app while Rex answers, and wait until the answer finishes.
- Speak a follow-up while Rex is still minimized.
- Reopen Rex and confirm it is not in the fatal `Issue` screen.
- VPS logs should show a clean close/open cycle between turns, with no backend traceback.

### 2026-05-22 - Native iOS endpointing cut pauses and long context

Result: `fail -> fixed in code`

Observed behavior:

- If the user waited around 30 seconds before speaking, Rex could stop the native listening turn.
- Native iOS also ended the user turn too quickly during natural pauses, cutting off longer context.

Likely cause:

- Native endpointing was stricter than the older Flutter streaming path.
- The native max utterance window was only 20 seconds and started when listening began, not when speech began.
- The native no-speech timeout emitted `utterance.end`, creating an empty turn instead of continuing to listen.

Fix:

- Native max utterance duration is now 90 seconds, counted from speech start.
- Native silence-after-speech tolerance is now 5 seconds.
- Native speech/silence thresholds are more tolerant of quieter words.
- Native no-speech timeout now emits a non-fatal idle status event and keeps listening instead of sending `utterance.end`.

Follow-up adjustment:

- Native max utterance duration is now 180 seconds, counted from speech start.
- Native silence-after-speech tolerance is now 10 seconds.
- Native speech/silence thresholds were loosened again to avoid endpointing during breaths or softer second phrases.

Retest required:

- Start a release call with native iOS voice enabled.
- Wait at least 45 seconds before speaking; Rex should still listen.
- Speak a long message with 6-8 second pauses; Rex should not cut the turn early.
- Speak for close to 180 seconds; Rex should still eventually endpoint instead of recording forever.

Follow-up root cause:

- Real-device testing still showed mid-phrase cutoffs after native thresholds were loosened.
- Backend live Deepgram events could still auto-start a turn on `speech_final` or transcript idle.
- The iOS bridge also stopped capture on any `transcript.final` event.

Additional fix:

- Native iOS sessions now require explicit `utterance.end` from the phone before the backend starts Rex's response.
- Backend live transcript idle and Deepgram `speech_final` auto-processing are disabled for `client: ios_native`.
- Native `transcript.final` updates visible transcript only; it no longer stops microphone capture or moves the call to `Thinking`.

Follow-up tuning:

- Native transcript final chunks are appended into one normalized visible utterance instead of replacing the previous line.
- Native endpointing uses a 5.5 second silence window with a stricter -60 dB silence threshold so quiet room noise does not keep Rex stuck in Listening forever.
