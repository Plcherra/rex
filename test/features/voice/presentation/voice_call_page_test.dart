import 'dart:async';

import 'package:audio_session/audio_session.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:rex/core/rex_app.dart';
import 'package:rex/features/voice/application/voice_call_controller.dart';
import 'package:rex/features/voice/application/voice_controller.dart';
import 'package:rex/features/voice/data/audio_capture_service.dart';
import 'package:rex/features/voice/data/audio_playback_service.dart';
import 'package:rex/features/voice/data/audio_recording_service.dart';
import 'package:rex/features/voice/data/audio_session_service.dart';
import 'package:rex/features/voice/data/background_voice_service.dart';
import 'package:rex/features/voice/data/cloud_voice_api.dart';
import 'package:rex/features/voice/domain/voice_call_state.dart';
import 'package:rex/features/voice/presentation/pages/voice_call_page.dart';

void main() {
  testWidgets('ChatPage opens active voice call page', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: voiceCallWidgetOverrides(),
        child: const RexApp(),
      ),
    );

    await tester.tap(find.byTooltip('Call Rex'));
    await tester.pumpAndSettle();

    expect(find.text('Call Rex'), findsOneWidget);
    expect(find.text('Listening'), findsOneWidget);
    expect(find.byTooltip('Mute mic'), findsOneWidget);
    expect(find.byTooltip('End call'), findsOneWidget);
  });

  testWidgets('VoiceCallPage renders idle state when auto start is disabled', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: voiceCallWidgetOverrides(),
        child: MaterialApp(home: VoiceCallPage(autoStart: false)),
      ),
    );

    expect(find.text('Ready to call'), findsOneWidget);
    expect(find.text('Start call'), findsOneWidget);

    await tester.tap(find.text('Start call'));
    await tester.pumpAndSettle();

    expect(find.text('Listening'), findsOneWidget);
  });

  testWidgets('VoiceCallPage toggles muted call UI', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: voiceCallWidgetOverrides(),
        child: const MaterialApp(home: VoiceCallPage()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Listening'), findsOneWidget);
    await tester.tap(find.byTooltip('Mute mic'));
    await tester.pumpAndSettle();

    expect(find.text('Mic muted'), findsOneWidget);
    expect(find.byTooltip('Unmute mic'), findsOneWidget);
  });

  testWidgets('VoiceCallPage shows speaking content and can interrupt', (
    tester,
  ) async {
    final container = ProviderContainer(overrides: voiceCallWidgetOverrides());
    addTearDown(container.dispose);
    final controller = container.read(voiceCallProvider.notifier);
    await controller.startCall();
    controller.startThinking(finalTranscript: 'I need direct advice.');
    controller.startSpeaking('Stop repeating the same pattern.');

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: VoiceCallPage(autoStart: false)),
      ),
    );

    expect(find.text('Speaking'), findsOneWidget);
    expect(find.text('I need direct advice.'), findsOneWidget);
    expect(find.text('Stop repeating the same pattern.'), findsOneWidget);

    await tester.tap(find.byTooltip('Interrupt Rex'));
    await tester.pumpAndSettle();

    final state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.listening);
    expect(find.text('Listening'), findsOneWidget);
  });

  testWidgets('VoiceCallPage renders failed state with retry action', (
    tester,
  ) async {
    final container = ProviderContainer(overrides: voiceCallWidgetOverrides());
    addTearDown(container.dispose);
    final controller = container.read(voiceCallProvider.notifier);
    await controller.startCall();
    controller.fail('Network dropped.');

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: VoiceCallPage(autoStart: false)),
      ),
    );

    expect(find.text('Call failed'), findsOneWidget);
    expect(find.text('Network dropped.'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);

    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();

    expect(find.text('Listening'), findsOneWidget);
  });
}

List<Override> voiceCallWidgetOverrides() {
  return [
    microphonePermissionProvider.overrideWithValue(
      _FakeMicrophonePermissionService(),
    ),
    audioCaptureServiceProvider.overrideWithValue(_FakeAudioCaptureService()),
    audioPlaybackServiceProvider.overrideWithValue(_FakeAudioPlaybackService()),
    voiceAudioSessionServiceProvider.overrideWithValue(
      _FakeVoiceAudioSessionService(),
    ),
    backgroundVoiceServiceProvider.overrideWithValue(
      _FakeBackgroundVoiceService(),
    ),
    cloudVoiceApiProvider.overrideWithValue(_FakeCloudVoiceApi()),
  ];
}

class _FakeMicrophonePermissionService implements MicrophonePermissionService {
  @override
  Future<void> openSettings() async {}

  @override
  Future<MicrophonePermissionDecision> requestMicrophonePermission({
    bool includeSpeechRecognition = true,
  }) async {
    return MicrophonePermissionDecision.granted;
  }
}

class _FakeAudioCaptureService implements AudioCaptureService {
  @override
  Future<RecordedVoiceAudio?> captureUtterance({
    required VoiceCaptureConfig config,
    required SpeechStartCallback onSpeechStart,
  }) {
    return Completer<RecordedVoiceAudio?>().future;
  }

  @override
  Future<void> cancel() async {}
}

class _FakeAudioPlaybackService implements AudioPlaybackService {
  @override
  Future<void> pause() async {}

  @override
  Future<void> playBase64Audio(
    String audioBase64, {
    required String contentType,
    required AudioPlaybackCompleteCallback onComplete,
    required AudioPlaybackErrorCallback onError,
  }) async {}

  @override
  Future<void> stop() async {}
}

class _FakeVoiceAudioSessionService implements VoiceAudioSessionService {
  @override
  Future<void> configureForVoiceTurn() async {}

  @override
  StreamSubscription<AudioInterruptionEvent> listenForInterruptions(
    onInterrupted,
  ) {
    return const Stream<AudioInterruptionEvent>.empty().listen((_) {});
  }

  @override
  StreamSubscription<void> listenForNoisyAudio(onInterrupted) {
    return const Stream<void>.empty().listen((_) {});
  }

  @override
  Future<void> setActive(bool active) async {}
}

class _FakeBackgroundVoiceService implements BackgroundVoiceService {
  @override
  Future<void> start() async {}

  @override
  Future<void> stop() async {}
}

class _FakeCloudVoiceApi extends CloudVoiceApi {}
