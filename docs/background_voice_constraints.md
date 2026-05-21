# Background Voice Constraints

## Goal
Document what Rex can realistically support for street, pocket, and locked-screen voice before deeper native work.

## Current Target
Rex should keep a streaming voice session alive as far as the operating system allows:

```text
iPhone microphone
-> Flutter streams audio frames
-> FastAPI WebSocket voice session
-> Deepgram live transcription
-> Grok streaming response
-> Google TTS audio chunks
-> iPhone speaker playback
-> return to listening without closing the session
```

The upload-per-turn route remains a fallback. The Phase 5 implementation prepares the app for streaming by configuring mobile audio sessions, Android foreground-service declarations, and interruption handling. Physical-device testing is still required.

## 2026-05-21 Device Scan Result
`flutter devices` found one physical iPhone available for validation:

```text
Pedro Martins (mobile) - iOS 26.5 23F77 - 00008150-000C03C83A2B401C
```

No physical Android device was connected during this scan, so Android background voice validation is blocked until one is available.

Physical iPhone testing showed that the current streaming call can stop hearing the user when the screen is locked or the app is backgrounded. This is not a missing `Info.plist` permission: the app already declares microphone access and `UIBackgroundModes/audio`. The remaining gap is that the active microphone capture and WebSocket streaming path still run through Flutter/Dart (`record.startStream` -> WebSocket). iOS can suspend that Dart path when the app leaves the foreground.

The active call controller now restarts the listening stream on app resume so app switching does not leave Rex silently stuck. That is a recovery fix, not a full locked-screen native voice implementation.

Real iPhone testing also found a separate state-machine bug: if Rex entered `thinking` while the app was backgrounded, it could capture the user's background speech but never receive or process the assistant response events, leaving the UI stuck on `Thinking` for several minutes after reopening. The controller now has a thinking watchdog that interrupts the stale stream and returns to `Listening` with a recoverable error message. This prevents indefinite hangs, but it still does not replace native locked-screen voice ownership.

Follow-up iPhone testing showed a related locked-screen behavior: Rex can buffer the user's words while the screen is locked, but Dart-side silence detection may not transition to `thinking` until the phone is unlocked. On resume, Rex now submits any buffered transcript by ending the active streaming utterance instead of canceling and restarting the stream. This improves unlock recovery, but true processing while still locked remains native work.

Follow-up app-switch testing found a client-to-backend pipeline issue: the UI could move to `Thinking` when speech endpointing fired, while the actual `utterance.end` WebSocket event was delayed until the recorder future returned. If iOS paused that Dart continuation after the app was minimized, the VPS never received the turn boundary, so Rex had no reason to start the assistant response. The controller now sends `utterance.end` immediately inside the speech-ended callback and keeps the later cleanup path guarded so the event is sent only once.

Further iPhone testing showed that the first minimized follow-up turn can work, but Rex may fail after speaking if it tries to start the next microphone stream while still backgrounded. The call controller now treats that recorder restart failure as a background recovery case instead of a fatal call failure: it keeps the call active, closes the stale stream, and restarts listening when the app returns to the foreground.

The physical-device validation checklist is tracked in `docs/testing/background_voice_checklist.md`.

## iOS Constraints
Apple allows background audio behavior when the app declares `UIBackgroundModes` with `audio` and configures the audio session correctly. For Rex, the right first configuration is:

- `AVAudioSessionCategoryPlayAndRecord`
- `AVAudioSessionModeVoiceChat`
- Bluetooth allowed
- Speaker fallback enabled
- Background audio mode enabled in `Info.plist`

Important limits:

- iOS may still interrupt recording for calls, Siri, route changes, and system policy.
- The simulator is not a reliable test for locked-screen voice.
- App Store review may require the background audio behavior to be clearly user-facing and justified.
- Long-running always-on listening is not the same as a user-started voice turn. Rex should start from an explicit user action.

## Android Constraints
Android microphone access is while-in-use restricted. For background/pocket recording:

- The app needs `RECORD_AUDIO`.
- The app needs foreground-service declarations.
- The app should start a foreground service while Rex is actively recording.
- The foreground service must show a visible notification.
- Android may block microphone access if a microphone foreground service is started from the background.

Phase 5 adds the manifest permissions and a minimal native foreground service. Full reliability still requires testing on physical Android devices across OS versions.

## Bluetooth And Route Changes
Bluetooth headphones, speaker changes, and unplugged wired headphones can interrupt or reroute audio. Rex should:

- Configure the audio session before recording/playback.
- Stop or fail clearly when audio becomes noisy or interrupted.
- Let the user restart the voice turn without stale state.

## What Is Realistic Now
Expected after Phase 5:

- Foreground voice turns are stronger.
- iOS has the correct background-audio declaration and audio session.
- Android has the foreground-service foundation.
- Interruptions no longer leave Rex silently stuck.

Not guaranteed until physical-device validation:

- Long locked-screen recordings on iPhone.
- Long background microphone capture on Android.
- Bluetooth stability across all devices.
- OS-specific edge cases during incoming calls or network loss.

Requires deeper native work:

- iOS locked-screen voice needs a native `AVAudioEngine`/`AVAudioSession` capture path that owns recording while the app is backgrounded, then bridges audio/transcript events back to Flutter.
- Android locked-screen voice should move microphone ownership into the foreground service, not just show a notification while Flutter owns capture.
- Flutter/Dart lifecycle handling can recover after resume, but it should not be treated as proof of continuous background capture.

## Physical Test Checklist
- iPhone foreground voice turn.
- iPhone lock screen during recording.
- iPhone app switch during thinking/playback.
- Android foreground voice turn.
- Android minimize app during recording after foreground service starts.
- Bluetooth headphones connected/disconnected mid-turn.
- Incoming call or notification interruption.
- Network drop during Deepgram/Grok/Google TTS.

## References
- Apple: `AVAudioSession` and background audio require the audio background mode for lock-screen playback/recording behavior.
- Android: microphone foreground services require the microphone foreground-service type, and microphone access is constrained by while-in-use permission rules.

## Revision History
- 2026-05-21 - Kept background recorder restart failures recoverable instead of ending the voice call.
- 2026-05-21 - Fixed app-switch pipeline bug by sending `utterance.end` immediately when speech endpointing fires; retest required on iPhone release build.
- 2026-05-21 - Documented and fixed iPhone background thinking deadlock with a controller watchdog; retest required on release build.
- 2026-05-21 - Added physical validation checklist path and latest device inventory; Android validation is blocked until a real device is connected.
- 2026-05-21 - Added real-device scan result: active Flutter streaming does not reliably survive iPhone lock/background; resume recovery added, native capture still required.
- 2026-05-15 - Initial background voice constraints for Rex Phase 5.
