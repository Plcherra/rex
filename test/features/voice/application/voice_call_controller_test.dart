import 'dart:async';
import 'dart:typed_data';

import 'package:audio_session/audio_session.dart';
import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/voice/application/voice_call_controller.dart';
import 'package:rex/features/voice/application/voice_controller.dart';
import 'package:rex/features/voice/data/audio_capture_service.dart';
import 'package:rex/features/voice/data/audio_playback_service.dart';
import 'package:rex/features/voice/data/audio_recording_service.dart';
import 'package:rex/features/voice/data/audio_session_service.dart';
import 'package:rex/features/voice/data/background_voice_service.dart';
import 'package:rex/features/voice/data/cloud_voice_api.dart';
import 'package:rex/features/voice/domain/voice_call_state.dart';

void main() {
  test('VoiceCallState exposes active, busy, and startable phases', () {
    expect(const VoiceCallState().isIdle, true);
    expect(const VoiceCallState().canStartCall, true);
    expect(const VoiceCallState().isCallActive, false);
    expect(const VoiceCallState().isBusy, false);

    expect(
      const VoiceCallState(phase: VoiceCallPhase.listening).isCallActive,
      true,
    );
    expect(
      const VoiceCallState(phase: VoiceCallPhase.capturingSpeech).isBusy,
      false,
    );
    expect(
      const VoiceCallState(phase: VoiceCallPhase.endpointing).isBusy,
      true,
    );
    expect(const VoiceCallState(phase: VoiceCallPhase.thinking).isBusy, true);
    expect(const VoiceCallState(phase: VoiceCallPhase.speaking).isBusy, true);
    expect(
      const VoiceCallState(phase: VoiceCallPhase.failed).canStartCall,
      true,
    );
    expect(
      const VoiceCallState(phase: VoiceCallPhase.ended).canStartCall,
      true,
    );
  });

  test('VoiceCallState calculates call duration safely', () {
    final startedAt = DateTime.utc(2026, 5, 17, 2);
    final state = VoiceCallState(
      phase: VoiceCallPhase.listening,
      callStartedAt: startedAt,
    );

    expect(
      state.callDuration(now: DateTime.utc(2026, 5, 17, 2, 3)),
      const Duration(minutes: 3),
    );
    expect(
      state.callDuration(now: DateTime.utc(2026, 5, 17, 1, 59)),
      Duration.zero,
    );
    expect(const VoiceCallState().callDuration(), Duration.zero);
  });

  test(
    'VoiceCallController starts a call with active conversation context',
    () async {
      final now = DateTime.utc(2026, 5, 17, 2, 15);
      final container = voiceCallTestContainer(
        overrides: [voiceCallNowProvider.overrideWithValue(() => now)],
      );
      addTearDown(container.dispose);
      container.read(chatProvider.notifier).setConversationId('conversation-1');

      final started = await container
          .read(voiceCallProvider.notifier)
          .startCall();
      final state = container.read(voiceCallProvider);

      expect(started, true);
      expect(state.phase, VoiceCallPhase.listening);
      expect(state.conversationId, 'conversation-1');
      expect(state.callStartedAt, now);
      expect(state.isCallActive, true);
    },
  );

  test('VoiceCallController ignores duplicate starts while active', () async {
    final container = voiceCallTestContainer();
    addTearDown(container.dispose);

    final controller = container.read(voiceCallProvider.notifier);
    expect(await controller.startCall(conversationId: 'conversation-1'), true);
    expect(await controller.startCall(conversationId: 'conversation-2'), false);

    final state = container.read(voiceCallProvider);
    expect(state.conversationId, 'conversation-1');
    expect(state.phase, VoiceCallPhase.listening);
  });

  test(
    'VoiceCallController tracks capture, endpoint, and thinking states',
    () async {
      final container = voiceCallTestContainer();
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      await controller.startCall();
      controller.startCapturingSpeech(transcript: 'Hey Rex');
      expect(
        container.read(voiceCallProvider).phase,
        VoiceCallPhase.capturingSpeech,
      );
      expect(container.read(voiceCallProvider).currentTranscript, 'Hey Rex');

      controller.updateTranscript('Hey Rex, help me think.');
      expect(
        container.read(voiceCallProvider).currentTranscript,
        'Hey Rex, help me think.',
      );

      controller.endpointUtterance();
      expect(
        container.read(voiceCallProvider).phase,
        VoiceCallPhase.endpointing,
      );

      controller.startTranscribing();
      expect(
        container.read(voiceCallProvider).phase,
        VoiceCallPhase.transcribing,
      );

      controller.startThinking(finalTranscript: 'Hey Rex, help me think.');
      final state = container.read(voiceCallProvider);
      expect(state.phase, VoiceCallPhase.thinking);
      expect(state.currentTranscript, 'Hey Rex, help me think.');
    },
  );

  test('VoiceCallController returns to listening after speaking', () async {
    final container = voiceCallTestContainer();
    addTearDown(container.dispose);

    final controller = container.read(voiceCallProvider.notifier);
    await controller.startCall();
    controller.startThinking(finalTranscript: 'Tell me the truth.');
    controller.startSpeaking('You are repeating the same pattern.');

    var state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.speaking);
    expect(state.lastAssistantResponse, 'You are repeating the same pattern.');
    expect(state.currentTranscript, 'Tell me the truth.');

    controller.completeSpeaking();
    state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.listening);
    expect(state.currentTranscript, isEmpty);
    expect(state.lastAssistantResponse, 'You are repeating the same pattern.');
  });

  test('VoiceCallController supports interrupt and resume', () async {
    final container = voiceCallTestContainer();
    addTearDown(container.dispose);

    final controller = container.read(voiceCallProvider.notifier);
    await controller.startCall();
    controller.startSpeaking('Long answer.');
    controller.interrupt(reason: 'User interrupted Rex.');

    var state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.interrupted);
    expect(state.errorMessage, 'User interrupted Rex.');

    controller.resumeListening();
    state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.listening);
    expect(state.errorMessage, isNull);
  });

  test('VoiceCallController supports muting while call is active', () async {
    final captureService = FakeAudioCaptureService();
    final container = voiceCallTestContainer(captureService: captureService);
    addTearDown(container.dispose);

    final controller = container.read(voiceCallProvider.notifier);
    controller.toggleMuted();
    expect(container.read(voiceCallProvider).isMuted, false);

    await controller.startCall();
    controller.toggleMuted();
    expect(container.read(voiceCallProvider).isMuted, true);
    expect(captureService.cancelCount, greaterThanOrEqualTo(1));

    controller.setMuted(false);
    expect(container.read(voiceCallProvider).isMuted, false);
  });

  test('VoiceCallController fails and ends calls with timestamps', () async {
    final start = DateTime.utc(2026, 5, 17, 2, 15);
    final failure = DateTime.utc(2026, 5, 17, 2, 16);
    var now = start;
    final container = voiceCallTestContainer(
      overrides: [voiceCallNowProvider.overrideWithValue(() => now)],
    );
    addTearDown(container.dispose);

    final controller = container.read(voiceCallProvider.notifier);
    await controller.startCall();
    now = failure;
    controller.fail('Network failed.');

    var state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.failed);
    expect(state.errorMessage, 'Network failed.');
    expect(state.callEndedAt, failure);
    expect(state.callDuration(), const Duration(minutes: 1));

    now = DateTime.utc(2026, 5, 17, 2, 20);
    await controller.startCall(conversationId: 'conversation-2');
    controller.endCall();

    state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.ended);
    expect(state.conversationId, 'conversation-2');
    expect(state.callEndedAt, DateTime.utc(2026, 5, 17, 2, 20));
  });

  test('VoiceCallController can reset to a clean idle state', () async {
    final container = voiceCallTestContainer();
    addTearDown(container.dispose);

    final controller = container.read(voiceCallProvider.notifier);
    await controller.startCall(conversationId: 'conversation-1');
    controller.startSpeaking('Answer.');
    controller.reset();

    final state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.idle);
    expect(state.conversationId, isNull);
    expect(state.lastAssistantResponse, isEmpty);
  });

  test(
    'VoiceCallController endpoints and sends a captured voice turn',
    () async {
      final captureService = FakeAudioCaptureService();
      final playbackService = FakeAudioPlaybackService();
      final api = FakeCloudVoiceApi();
      final container = voiceCallTestContainer(
        captureService: captureService,
        playbackService: playbackService,
        cloudVoiceApi: api,
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      expect(
        await controller.startCall(conversationId: 'conversation-1'),
        true,
      );
      await pumpEventQueue();

      captureService.triggerSpeechStart();
      expect(
        container.read(voiceCallProvider).phase,
        VoiceCallPhase.capturingSpeech,
      );

      captureService.completeWithAudio();
      await pumpEventQueue();

      var state = container.read(voiceCallProvider);
      expect(state.phase, VoiceCallPhase.speaking);
      expect(state.currentTranscript, 'Hey Rex');
      expect(state.lastAssistantResponse, 'Rex answer');
      expect(api.receivedConversationId, 'conversation-1');
      expect(playbackService.playedAudioBase64, 'bXAzLWJ5dGVz');
      expect(container.read(chatProvider).conversationId, 'conversation-1');

      playbackService.complete();
      await pumpEventQueue();

      state = container.read(voiceCallProvider);
      expect(state.phase, VoiceCallPhase.listening);
      expect(state.currentTranscript, isEmpty);
    },
  );

  test(
    'VoiceEndpointDetector detects speech, silence, and no-speech timeout',
    () {
      final config = VoiceCaptureConfig(
        noSpeechTimeout: const Duration(seconds: 2),
        silenceAfterSpeech: const Duration(milliseconds: 500),
        minSpeechDuration: const Duration(milliseconds: 100),
      );
      final startedAt = DateTime.utc(2026, 5, 17, 2);
      final detector = VoiceEndpointDetector(
        config: config,
        startedAt: startedAt,
      );

      var update = detector.addAmplitude(
        currentDb: -60,
        now: startedAt.add(const Duration(seconds: 1)),
      );
      expect(update.noSpeechTimedOut, false);

      update = detector.addAmplitude(
        currentDb: -36,
        now: startedAt.add(const Duration(milliseconds: 1200)),
      );
      expect(update.speechStarted, true);

      update = detector.addAmplitude(
        currentDb: -60,
        now: startedAt.add(const Duration(milliseconds: 1900)),
      );
      expect(update.endpointReached, true);

      final silentDetector = VoiceEndpointDetector(
        config: config,
        startedAt: startedAt,
      );
      update = silentDetector.addAmplitude(
        currentDb: -60,
        now: startedAt.add(const Duration(seconds: 3)),
      );
      expect(update.noSpeechTimedOut, true);
    },
  );
}

ProviderContainer voiceCallTestContainer({
  FakeAudioCaptureService? captureService,
  FakeAudioPlaybackService? playbackService,
  FakeCloudVoiceApi? cloudVoiceApi,
  List<Override> overrides = const [],
}) {
  return ProviderContainer(
    overrides: [
      ...voiceCallTestOverrides(
        captureService: captureService,
        playbackService: playbackService,
        cloudVoiceApi: cloudVoiceApi,
      ),
      ...overrides,
    ],
  );
}

List<Override> voiceCallTestOverrides({
  FakeAudioCaptureService? captureService,
  FakeAudioPlaybackService? playbackService,
  FakeCloudVoiceApi? cloudVoiceApi,
}) {
  return [
    microphonePermissionProvider.overrideWithValue(
      FakeMicrophonePermissionService(),
    ),
    audioCaptureServiceProvider.overrideWithValue(
      captureService ?? FakeAudioCaptureService(),
    ),
    audioPlaybackServiceProvider.overrideWithValue(
      playbackService ?? FakeAudioPlaybackService(),
    ),
    voiceAudioSessionServiceProvider.overrideWithValue(
      FakeVoiceAudioSessionService(),
    ),
    backgroundVoiceServiceProvider.overrideWithValue(
      FakeBackgroundVoiceService(),
    ),
    cloudVoiceApiProvider.overrideWithValue(
      cloudVoiceApi ?? FakeCloudVoiceApi(),
    ),
  ];
}

class FakeMicrophonePermissionService implements MicrophonePermissionService {
  @override
  Future<void> openSettings() async {}

  @override
  Future<MicrophonePermissionDecision> requestMicrophonePermission({
    bool includeSpeechRecognition = true,
  }) async {
    return MicrophonePermissionDecision.granted;
  }
}

class FakeAudioCaptureService implements AudioCaptureService {
  Completer<RecordedVoiceAudio?>? _completer;
  SpeechStartCallback? _onSpeechStart;
  var cancelCount = 0;

  @override
  Future<RecordedVoiceAudio?> captureUtterance({
    required VoiceCaptureConfig config,
    required SpeechStartCallback onSpeechStart,
  }) {
    _onSpeechStart = onSpeechStart;
    _completer = Completer<RecordedVoiceAudio?>();
    return _completer!.future;
  }

  @override
  Future<void> cancel() async {
    cancelCount++;
    if (_completer != null && !_completer!.isCompleted) {
      _completer!.complete(null);
    }
  }

  void triggerSpeechStart() {
    _onSpeechStart?.call();
  }

  void completeWithAudio() {
    _completer?.complete(
      RecordedVoiceAudio(
        file: XFile.fromData(
          Uint8List.fromList([1, 2, 3]),
          name: 'voice.m4a',
          mimeType: 'audio/mp4',
        ),
        inputMimeType: 'audio/mp4',
      ),
    );
  }
}

class FakeAudioPlaybackService implements AudioPlaybackService {
  AudioPlaybackCompleteCallback? _onComplete;
  String? playedAudioBase64;

  @override
  Future<void> playBase64Audio(
    String audioBase64, {
    required String contentType,
    required AudioPlaybackCompleteCallback onComplete,
    required AudioPlaybackErrorCallback onError,
  }) async {
    playedAudioBase64 = audioBase64;
    _onComplete = onComplete;
  }

  @override
  Future<void> pause() async {}

  @override
  Future<void> stop() async {}

  void complete() {
    _onComplete?.call();
  }
}

class FakeVoiceAudioSessionService implements VoiceAudioSessionService {
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

class FakeBackgroundVoiceService implements BackgroundVoiceService {
  @override
  Future<void> start() async {}

  @override
  Future<void> stop() async {}
}

class FakeCloudVoiceApi extends CloudVoiceApi {
  String? receivedConversationId;

  @override
  Future<CloudVoiceTurnResponse> sendVoiceTurn({
    required XFile audio,
    required String inputMimeType,
    String? conversationId,
  }) async {
    receivedConversationId = conversationId;
    return const CloudVoiceTurnResponse(
      conversationId: 'conversation-1',
      transcript: 'Hey Rex',
      responseText: 'Rex answer',
      audioContentType: 'audio/mpeg',
      audioBase64: 'bXAzLWJ5dGVz',
      audioEncoding: 'MP3',
      voiceName: 'en-US-Neural2-J',
      languageCode: 'en-US',
    );
  }
}
