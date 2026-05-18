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
- 2026-05-15 - Initial background voice constraints for Rex Phase 5.
