import 'dart:async';

import 'package:audio_session/audio_session.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rex/features/voice/application/voice_controller.dart';
import 'package:rex/features/voice/data/audio_playback_service.dart';
import 'package:rex/features/voice/data/audio_session_service.dart';
import 'package:rex/features/voice/data/background_voice_service.dart';
import 'package:rex/features/voice/data/speech_to_text_service.dart';
import 'package:rex/features/voice/data/text_to_speech_service.dart';
import 'package:rex/features/voice/domain/voice_state.dart';
import 'package:rex/features/voice/presentation/widgets/voice_recorder_sheet.dart';

class FakeMicrophonePermissionService implements MicrophonePermissionService {
  FakeMicrophonePermissionService(this.decision);

  final MicrophonePermissionDecision decision;
  var requestCount = 0;
  var openSettingsCount = 0;

  @override
  Future<MicrophonePermissionDecision> requestMicrophonePermission({
    bool includeSpeechRecognition = true,
  }) async {
    requestCount++;
    return decision;
  }

  @override
  Future<void> openSettings() async {
    openSettingsCount++;
  }
}

class FakeSpeechToTextService implements SpeechToTextService {
  var initializeCount = 0;
  var startListeningCount = 0;
  var stopListeningCount = 0;
  var cancelCount = 0;
  SpeechTranscriptCallback? onPartialTranscript;
  SpeechTranscriptCallback? onFinalTranscript;
  SpeechErrorCallback? onError;

  @override
  Future<bool> initialize({required SpeechErrorCallback onError}) async {
    initializeCount++;
    this.onError = onError;
    return true;
  }

  @override
  Future<void> startListening({
    required SpeechTranscriptCallback onPartialTranscript,
    required SpeechTranscriptCallback onFinalTranscript,
    required SpeechErrorCallback onError,
  }) async {
    startListeningCount++;
    this.onPartialTranscript = onPartialTranscript;
    this.onFinalTranscript = onFinalTranscript;
    this.onError = onError;
  }

  @override
  Future<void> stopListening() async {
    stopListeningCount++;
  }

  @override
  Future<void> cancel() async {
    cancelCount++;
  }

  void emitPartialTranscript(String transcript) {
    onPartialTranscript?.call(transcript);
  }

  void emitError(String message) {
    onError?.call(message);
  }
}

class FakeTextToSpeechService implements TextToSpeechService {
  var speakCount = 0;
  var stopCount = 0;
  String? spokenText;
  TextToSpeechCompleteCallback? onComplete;
  TextToSpeechErrorCallback? onError;

  @override
  Future<void> speak(
    String text, {
    required TextToSpeechCompleteCallback onComplete,
    required TextToSpeechErrorCallback onError,
  }) async {
    speakCount++;
    spokenText = text;
    this.onComplete = onComplete;
    this.onError = onError;
  }

  @override
  Future<void> stop() async {
    stopCount++;
  }

  @override
  Future<void> pause() async {}

  void complete() {
    onComplete?.call();
  }

  void emitError(String message) {
    onError?.call(message);
  }
}

class FakeAudioPlaybackService implements AudioPlaybackService {
  var stopCount = 0;

  @override
  Future<void> playBase64Audio(
    String audioBase64, {
    required String contentType,
    required AudioPlaybackCompleteCallback onComplete,
    required AudioPlaybackErrorCallback onError,
  }) async {}

  @override
  Future<void> stop() async {
    stopCount++;
  }

  @override
  Future<void> pause() async {}
}

class FakeVoiceAudioSessionService implements VoiceAudioSessionService {
  @override
  Future<void> configureForVoiceTurn() async {}

  @override
  Future<void> setActive(bool active) async {}

  @override
  StreamSubscription<void> listenForNoisyAudio(
    VoiceAudioInterruptionCallback onInterrupted,
  ) {
    return const Stream<void>.empty().listen((_) {});
  }

  @override
  StreamSubscription<AudioInterruptionEvent> listenForInterruptions(
    VoiceAudioInterruptionCallback onInterrupted,
  ) {
    return const Stream<AudioInterruptionEvent>.empty().listen((_) {});
  }
}

class FakeBackgroundVoiceService implements BackgroundVoiceService {
  @override
  Future<void> start() async {}

  @override
  Future<void> stop() async {}
}

void main() {
  testWidgets('VoiceRecorderSheet renders idle state and can start listening', (
    tester,
  ) async {
    final permissionService = FakeMicrophonePermissionService(
      MicrophonePermissionDecision.granted,
    );
    final speechToTextService = FakeSpeechToTextService();
    final container = _container(
      permissionService: permissionService,
      speechToTextService: speechToTextService,
    );
    addTearDown(container.dispose);

    await _pumpSheet(tester, container);

    expect(find.text('Ready when you are'), findsOneWidget);
    expect(find.text('Start talking'), findsOneWidget);

    await tester.tap(find.text('Start talking'));
    await tester.pump();

    expect(permissionService.requestCount, 1);
    expect(speechToTextService.startListeningCount, 1);
    expect(find.text('Listening'), findsOneWidget);
  });

  testWidgets(
    'VoiceRecorderSheet shows live partial transcript while listening',
    (tester) async {
      final speechToTextService = FakeSpeechToTextService();
      final container = _container(speechToTextService: speechToTextService);
      addTearDown(container.dispose);

      await _pumpSheet(tester, container);
      await container.read(voiceProvider.notifier).startListening();
      speechToTextService.emitPartialTranscript('I need real advice');
      await tester.pump();

      expect(find.text('Listening'), findsOneWidget);
      expect(find.text('I need real advice'), findsOneWidget);
      expect(find.text('Stop'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
    },
  );

  testWidgets('VoiceRecorderSheet renders transcribing and thinking states', (
    tester,
  ) async {
    final container = _container();
    addTearDown(container.dispose);

    await _pumpSheet(tester, container);

    container
        .read(voiceProvider.notifier)
        .finishTranscription('Send this transcript');
    await tester.pump();

    expect(find.text('Transcribing'), findsOneWidget);
    expect(find.text('Send this transcript'), findsOneWidget);
    expect(find.text('Cancel'), findsOneWidget);

    container.read(voiceProvider.notifier).startThinking();
    await tester.pump();

    expect(find.text('Thinking'), findsOneWidget);
    expect(find.text('Cancel'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('VoiceRecorderSheet renders speaking state and stops playback', (
    tester,
  ) async {
    final textToSpeechService = FakeTextToSpeechService();
    final container = _container(textToSpeechService: textToSpeechService);
    addTearDown(container.dispose);

    await _pumpSheet(tester, container);
    await container
        .read(voiceProvider.notifier)
        .startSpeaking('This is Rex speaking.');
    await tester.pump();

    expect(find.text('Speaking'), findsOneWidget);
    expect(find.text('This is Rex speaking.'), findsOneWidget);
    expect(find.text('Stop playback'), findsOneWidget);

    await tester.tap(find.text('Stop playback'));
    await tester.pump();

    expect(textToSpeechService.stopCount, 1);
    expect(container.read(voiceProvider).phase, VoicePhase.idle);
  });

  testWidgets(
    'VoiceRecorderSheet renders failed and permission denied states',
    (tester) async {
      final container = _container();
      addTearDown(container.dispose);

      await _pumpSheet(tester, container);

      container.read(voiceProvider.notifier).fail('STT error.');
      await tester.pump();

      expect(find.text('Voice failed'), findsOneWidget);
      expect(find.text('STT error.'), findsWidgets);
      expect(find.text('Try again'), findsOneWidget);

      container.read(voiceProvider.notifier).denyPermission('Mic blocked.');
      await tester.pump();

      expect(find.text('Microphone blocked'), findsOneWidget);
      expect(find.text('Mic blocked.'), findsWidgets);
      expect(find.text('Try again'), findsOneWidget);
      expect(find.text('Open Settings'), findsOneWidget);
    },
  );

  testWidgets(
    'VoiceRecorderSheet opens Settings from permission denied state',
    (tester) async {
      final permissionService = FakeMicrophonePermissionService(
        MicrophonePermissionDecision.permanentlyDenied,
      );
      final container = _container(permissionService: permissionService);
      addTearDown(container.dispose);

      await _pumpSheet(tester, container);

      container.read(voiceProvider.notifier).denyPermission('Mic blocked.');
      await tester.pump();

      await tester.tap(find.text('Open Settings'));
      await tester.pump();

      expect(permissionService.openSettingsCount, 1);
    },
  );

  testWidgets('VoiceRecorderSheet cancel discards listening transcript', (
    tester,
  ) async {
    final speechToTextService = FakeSpeechToTextService();
    final container = _container(speechToTextService: speechToTextService);
    addTearDown(container.dispose);

    await _pumpSheet(tester, container);
    await container.read(voiceProvider.notifier).startListening();
    speechToTextService.emitPartialTranscript('Discard this');
    await tester.pump();

    await tester.tap(find.text('Cancel'));
    await tester.pump();

    final state = container.read(voiceProvider);
    expect(speechToTextService.cancelCount, 1);
    expect(state.phase, VoicePhase.idle);
    expect(state.partialTranscript, isEmpty);
    expect(state.finalTranscript, isEmpty);
    expect(find.text('Ready when you are'), findsOneWidget);
  });

  testWidgets('VoiceRecorderSheet explains empty simulator recordings', (
    tester,
  ) async {
    final speechToTextService = FakeSpeechToTextService();
    final container = _container(speechToTextService: speechToTextService);
    addTearDown(container.dispose);

    await _pumpSheet(tester, container);
    await container.read(voiceProvider.notifier).startListening();
    await tester.pump();

    await tester.tap(find.text('Stop'));
    await tester.pump();

    expect(speechToTextService.stopListeningCount, 1);
    expect(find.text('Voice failed'), findsOneWidget);
    expect(find.textContaining('I did not catch any audio'), findsWidgets);
    expect(find.textContaining('Simulator > I/O > Audio Input'), findsWidgets);
  });

  testWidgets('VoiceRecorderSheet surfaces STT and TTS errors', (tester) async {
    final speechToTextService = FakeSpeechToTextService();
    final textToSpeechService = FakeTextToSpeechService();
    final container = _container(
      speechToTextService: speechToTextService,
      textToSpeechService: textToSpeechService,
    );
    addTearDown(container.dispose);

    await _pumpSheet(tester, container);
    await container.read(voiceProvider.notifier).startListening();
    speechToTextService.emitError('Speech failed.');
    await tester.pump();

    expect(find.text('Voice failed'), findsOneWidget);
    expect(find.text('Speech failed.'), findsWidgets);

    await container.read(voiceProvider.notifier).startSpeaking('Talk');
    textToSpeechService.emitError('Playback failed.');
    await tester.pump();

    expect(find.text('Voice failed'), findsOneWidget);
    expect(find.text('Playback failed.'), findsWidgets);
  });
}

ProviderContainer _container({
  FakeMicrophonePermissionService? permissionService,
  FakeSpeechToTextService? speechToTextService,
  FakeTextToSpeechService? textToSpeechService,
  FakeAudioPlaybackService? audioPlaybackService,
}) {
  return ProviderContainer(
    overrides: [
      cloudVoiceEnabledProvider.overrideWithValue(false),
      microphonePermissionProvider.overrideWithValue(
        permissionService ??
            FakeMicrophonePermissionService(
              MicrophonePermissionDecision.granted,
            ),
      ),
      speechToTextServiceProvider.overrideWithValue(
        speechToTextService ?? FakeSpeechToTextService(),
      ),
      textToSpeechServiceProvider.overrideWithValue(
        textToSpeechService ?? FakeTextToSpeechService(),
      ),
      audioPlaybackServiceProvider.overrideWithValue(
        audioPlaybackService ?? FakeAudioPlaybackService(),
      ),
      voiceAudioSessionServiceProvider.overrideWithValue(
        FakeVoiceAudioSessionService(),
      ),
      backgroundVoiceServiceProvider.overrideWithValue(
        FakeBackgroundVoiceService(),
      ),
    ],
  );
}

Future<void> _pumpSheet(
  WidgetTester tester,
  ProviderContainer container,
) async {
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(body: VoiceRecorderSheet(autoStart: false)),
      ),
    ),
  );
}
