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

The app now attempts resume recovery when returning to foreground. That is useful, but it is not proof of continuous locked-screen voice. True lock-screen voice still requires native iOS microphone/WebSocket/playback ownership and Android service-owned microphone/WebSocket/playback.

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
| App switch while listening | User switches away and returns; Rex recovers without silent stuck state. | pending | Current controller has resume recovery. |
| App switch while Rex is thinking | Session does not crash; returning to app shows current state or clear failure. | pending | Watch for stale loading state. |
| App switch during TTS playback | Audio either continues or fails clearly; returning to app is recoverable. | pending | Playback is still Flutter-owned. |
| Screen lock while listening | Rex continues hearing a second utterance while locked. | fail | Known limitation with Flutter-owned capture. Native iOS session required. |
| Screen off after Rex speaks | Rex hears the next user utterance without reopening the app. | fail | Known limitation until native iOS capture/WebSocket exists. |
| Long response TTS playback | Long assistant answer plays without cutting off or corrupting state. | pending | Include at least 60 seconds of TTS. |
| AirPods or Bluetooth connected before call | Mic route and speaker route are correct. | pending | Note exact headset model. |
| Bluetooth route change mid-turn | Disconnect/connect headset during listening and playback. | pending | Should recover or fail clearly. |
| Incoming call interruption | Call interruption pauses/stops Rex cleanly and releases mic. | pending | Verify no zombie mic after interruption. |
| Notification interruption | Notification does not permanently break the voice session. | pending | Test while listening and speaking. |
| Network drop | Rex surfaces a clear error and can start a new session after network returns. | pending | Toggle Wi-Fi/cellular if safe. |
| Explicit hangup | Stop button releases mic/playback and backend session. | pending | Verify mic indicator turns off. |
| 3-5 minute session | Multiple turns continue without memory leak, stale state, or audio queue buildup. | pending | Foreground test first. |

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

