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
import 'package:rex/features/voice/data/streaming_audio_capture_service.dart';
import 'package:rex/features/voice/data/streaming_voice_api.dart';
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
    expect(const VoiceCallState(phase: VoiceCallPhase.thinking).isBusy, true);
    expect(const VoiceCallState(phase: VoiceCallPhase.speaking).isBusy, true);
    expect(
      const VoiceCallState(phase: VoiceCallPhase.failed).canStartCall,
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
    'VoiceCallController keeps capture internal and moves straight to thinking',
    () async {
      final container = voiceCallTestContainer();
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      await controller.startCall();
      controller.startCapturingSpeech(transcript: 'Hey Rex');
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.listening);
      expect(container.read(voiceCallProvider).currentTranscript, 'Hey Rex');

      controller.updateTranscript('Hey Rex, help me think.');
      expect(
        container.read(voiceCallProvider).currentTranscript,
        'Hey Rex, help me think.',
      );

      controller.endpointUtterance();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.thinking);

      controller.startTranscribing();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.thinking);

      controller.startThinking(finalTranscript: 'Hey Rex, help me think.');
      final state = container.read(voiceCallProvider);
      expect(state.phase, VoiceCallPhase.thinking);
      expect(state.currentTranscript, 'Hey Rex, help me think.');
    },
  );

  test('VoiceCallController accumulates live transcript segments', () async {
    final container = voiceCallTestContainer();
    addTearDown(container.dispose);

    final controller = container.read(voiceCallProvider.notifier);
    expect(await controller.startCall(conversationId: 'conversation-1'), true);

    controller.updateTranscript('I am planning something', isFinal: true);
    controller.updateTranscript('for next week');

    expect(
      container.read(voiceCallProvider).currentTranscript,
      'I am planning something for next week',
    );
    expect(container.read(voiceCallProvider).phase, VoiceCallPhase.listening);

    controller.startThinking(finalTranscript: 'a date on Friday');

    expect(
      container.read(voiceCallProvider).currentTranscript,
      'I am planning something for next week a date on Friday',
    );
    expect(container.read(voiceCallProvider).phase, VoiceCallPhase.thinking);
  });

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
    expect(state.phase, VoiceCallPhase.listening);
    expect(state.errorMessage, 'User interrupted Rex.');

    controller.resumeListening();
    state = container.read(voiceCallProvider);
    expect(state.phase, VoiceCallPhase.listening);
    expect(state.errorMessage, isNull);
  });

  test(
    'VoiceCallController interrupts speaking and listens again immediately',
    () async {
      final captureService = FakeAudioCaptureService();
      final playbackService = FakeAudioPlaybackService();
      final container = voiceCallTestContainer(
        captureService: captureService,
        playbackService: playbackService,
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      expect(
        await controller.startCall(conversationId: 'conversation-1'),
        true,
      );
      await pumpEventQueue();

      captureService.completeWithAudio();
      await pumpEventQueue();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.speaking);

      controller.interruptAndListen(reason: 'User wants to speak.');
      await pumpEventQueue();

      var state = container.read(voiceCallProvider);
      expect(state.phase, VoiceCallPhase.listening);
      expect(state.errorMessage, isNull);
      expect(state.currentTranscript, isEmpty);
      expect(playbackService.stopCount, greaterThanOrEqualTo(1));
      expect(captureService.captureCount, greaterThanOrEqualTo(2));

      playbackService.complete();
      await pumpEventQueue();

      state = container.read(voiceCallProvider);
      expect(state.phase, VoiceCallPhase.listening);
    },
  );

  test(
    'VoiceCallController interrupts pending thinking and ignores stale response',
    () async {
      final captureService = FakeAudioCaptureService();
      final playbackService = FakeAudioPlaybackService();
      final api = FakeCloudVoiceApi()..holdNextResponse();
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

      captureService.completeWithAudio();
      await pumpEventQueue();
      await Future<void>.delayed(const Duration(milliseconds: 300));
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.thinking);

      controller.interruptAndListen(reason: 'User wants to correct it.');
      await pumpEventQueue();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.listening);

      api.releaseHeldResponse();
      await pumpEventQueue();

      final state = container.read(voiceCallProvider);
      expect(state.phase, VoiceCallPhase.listening);
      expect(playbackService.playCount, 0);
      expect(state.lastAssistantResponse, isEmpty);
    },
  );

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
    expect(state.phase, VoiceCallPhase.idle);
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
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.listening);

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
    'VoiceCallController keeps returned conversation id across automatic turns',
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
      expect(await controller.startCall(), true);
      await pumpEventQueue();

      captureService.completeWithAudio();
      await pumpEventQueue();

      expect(api.receivedConversationIds, [null]);
      expect(
        container.read(voiceCallProvider).conversationId,
        'conversation-1',
      );

      playbackService.complete();
      await pumpEventQueue();

      captureService.completeWithAudio();
      await pumpEventQueue();

      expect(api.receivedConversationIds, [null, 'conversation-1']);
      expect(
        container.read(voiceCallProvider).conversationId,
        'conversation-1',
      );
    },
  );

  test(
    'VoiceCallController shows thinking immediately while a voice turn is pending',
    () async {
      final captureService = FakeAudioCaptureService();
      final api = FakeCloudVoiceApi()..holdNextResponse();
      final container = voiceCallTestContainer(
        captureService: captureService,
        cloudVoiceApi: api,
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      expect(
        await controller.startCall(conversationId: 'conversation-1'),
        true,
      );
      await pumpEventQueue();

      captureService.completeWithAudio();
      await pumpEventQueue();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.thinking);

      api.releaseHeldResponse();
      await pumpEventQueue();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.speaking);
    },
  );

  test(
    'VoiceCallController can use streaming voice transport when enabled',
    () async {
      final streamingCaptureService = FakeStreamingAudioCaptureService();
      final streamingApi = FakeStreamingVoiceApi();
      final playbackService = FakeAudioPlaybackService();
      final container = voiceCallTestContainer(
        playbackService: playbackService,
        streamingAudioCaptureService: streamingCaptureService,
        streamingVoiceApi: streamingApi,
        streamingVoiceEnabled: true,
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      expect(
        await controller.startCall(conversationId: 'conversation-1'),
        true,
      );
      await pumpEventQueue();
      await pumpEventQueue();

      final state = container.read(voiceCallProvider);
      expect(streamingApi.receivedConversationId, 'conversation-1');
      expect(streamingApi.session.sentAudioChunks.single, [1, 2, 3]);
      expect(streamingApi.session.utteranceEnded, true);
      expect(state.phase, VoiceCallPhase.speaking);
      expect(state.currentTranscript, 'Hey Rex');
      expect(state.lastAssistantResponse, 'Rex stream answer.');
      expect(playbackService.playedAudioBase64, 'bXAzLWJ5dGVz');
      expect(container.read(chatProvider).conversationId, 'conversation-1');
      expect(streamingApi.session.sessionEnded, false);
    },
  );

  test(
    'VoiceCallController interrupts streaming playback and notifies backend',
    () async {
      final streamingCaptureService = FakeStreamingAudioCaptureService();
      final streamingSession = FakeStreamingVoiceSession();
      final streamingApi = FakeStreamingVoiceApi(session: streamingSession);
      final playbackService = FakeAudioPlaybackService();
      final container = voiceCallTestContainer(
        playbackService: playbackService,
        streamingAudioCaptureService: streamingCaptureService,
        streamingVoiceApi: streamingApi,
        streamingVoiceEnabled: true,
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      expect(
        await controller.startCall(conversationId: 'conversation-1'),
        true,
      );
      await pumpEventQueue();
      await pumpEventQueue();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.speaking);

      controller.interruptAndListen(reason: 'User interrupted.');
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.listening);

      expect(streamingSession.interruptCount, 1);
      expect(playbackService.stopCount, greaterThanOrEqualTo(1));
      await pumpEventQueue();
      expect(streamingCaptureService.captureCount, greaterThanOrEqualTo(2));
    },
  );

  test(
    'VoiceCallController stops Rex when the user starts speaking over playback',
    () async {
      final streamingCaptureService = FakeStreamingAudioCaptureService();
      final streamingSession = FakeStreamingVoiceSession();
      final streamingApi = FakeStreamingVoiceApi(session: streamingSession);
      final playbackService = FakeAudioPlaybackService();
      final bargeInDetectionService = FakeBargeInDetectionService();
      final container = voiceCallTestContainer(
        playbackService: playbackService,
        streamingAudioCaptureService: streamingCaptureService,
        streamingVoiceApi: streamingApi,
        streamingVoiceEnabled: true,
        bargeInDetectionService: bargeInDetectionService,
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      expect(
        await controller.startCall(conversationId: 'conversation-1'),
        true,
      );
      await pumpEventQueue();
      await pumpEventQueue();

      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.speaking);
      expect(bargeInDetectionService.startCount, 1);

      bargeInDetectionService.triggerBargeIn();
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.listening);
      expect(streamingSession.interruptCount, 1);
      expect(playbackService.stopCount, greaterThanOrEqualTo(1));

      await pumpEventQueue();
      expect(streamingCaptureService.captureCount, greaterThanOrEqualTo(2));
    },
  );

  test(
    'VoiceCallController uses a fresh stream for each active call turn',
    () async {
      final streamingCaptureService = FakeStreamingAudioCaptureService();
      final streamingSession = FakeStreamingVoiceSession();
      final streamingApi = FakeStreamingVoiceApi(session: streamingSession);
      final playbackService = FakeAudioPlaybackService();
      final container = voiceCallTestContainer(
        playbackService: playbackService,
        streamingAudioCaptureService: streamingCaptureService,
        streamingVoiceApi: streamingApi,
        streamingVoiceEnabled: true,
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceCallProvider.notifier);
      expect(
        await controller.startCall(conversationId: 'conversation-1'),
        true,
      );
      await pumpEventQueue();
      await pumpEventQueue();

      expect(streamingApi.connectCount, 1);
      expect(streamingCaptureService.captureCount, 1);
      expect(streamingSession.utteranceEndCount, 1);
      expect(streamingSession.sessionEnded, false);
      expect(playbackService.playCount, 1);
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.speaking);

      playbackService.complete();
      await pumpEventQueue();
      await pumpEventQueue();

      expect(streamingApi.connectCount, 2);
      expect(streamingCaptureService.captureCount, 2);
      expect(streamingSession.sessionEnded, true);
      expect(streamingApi.sessions[1].utteranceEndCount, 1);
      expect(playbackService.playCount, 2);
      expect(
        container.read(voiceCallProvider).lastAssistantResponse,
        'Rex stream answer.',
      );
      expect(container.read(voiceCallProvider).phase, VoiceCallPhase.speaking);
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

  test('VoiceEndpointDetector default timing allows natural pauses', () {
    const config = VoiceCaptureConfig();
    final startedAt = DateTime.utc(2026, 5, 17, 2);
    final detector = VoiceEndpointDetector(
      config: config,
      startedAt: startedAt,
    );

    var update = detector.addAmplitude(
      currentDb: -40,
      now: startedAt.add(const Duration(milliseconds: 400)),
    );
    expect(update.speechStarted, true);

    update = detector.addAmplitude(
      currentDb: -70,
      now: startedAt.add(const Duration(milliseconds: 1000)),
    );
    expect(update.endpointReached, false);

    update = detector.addAmplitude(
      currentDb: -70,
      now: startedAt.add(const Duration(milliseconds: 1600)),
    );
    expect(update.endpointReached, true);
  });
}

ProviderContainer voiceCallTestContainer({
  FakeAudioCaptureService? captureService,
  FakeStreamingAudioCaptureService? streamingAudioCaptureService,
  FakeAudioPlaybackService? playbackService,
  FakeBargeInDetectionService? bargeInDetectionService,
  FakeCloudVoiceApi? cloudVoiceApi,
  FakeStreamingVoiceApi? streamingVoiceApi,
  bool streamingVoiceEnabled = false,
  List<Override> overrides = const [],
}) {
  return ProviderContainer(
    overrides: [
      ...voiceCallTestOverrides(
        captureService: captureService,
        streamingAudioCaptureService: streamingAudioCaptureService,
        playbackService: playbackService,
        bargeInDetectionService: bargeInDetectionService,
        cloudVoiceApi: cloudVoiceApi,
        streamingVoiceApi: streamingVoiceApi,
        streamingVoiceEnabled: streamingVoiceEnabled,
      ),
      ...overrides,
    ],
  );
}

List<Override> voiceCallTestOverrides({
  FakeAudioCaptureService? captureService,
  FakeStreamingAudioCaptureService? streamingAudioCaptureService,
  FakeAudioPlaybackService? playbackService,
  FakeBargeInDetectionService? bargeInDetectionService,
  FakeCloudVoiceApi? cloudVoiceApi,
  FakeStreamingVoiceApi? streamingVoiceApi,
  bool streamingVoiceEnabled = false,
}) {
  return [
    microphonePermissionProvider.overrideWithValue(
      FakeMicrophonePermissionService(),
    ),
    audioCaptureServiceProvider.overrideWithValue(
      captureService ?? FakeAudioCaptureService(),
    ),
    streamingAudioCaptureServiceProvider.overrideWithValue(
      streamingAudioCaptureService ?? FakeStreamingAudioCaptureService(),
    ),
    audioPlaybackServiceProvider.overrideWithValue(
      playbackService ?? FakeAudioPlaybackService(),
    ),
    bargeInDetectionServiceProvider.overrideWithValue(
      bargeInDetectionService ?? FakeBargeInDetectionService(),
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
    streamingVoiceApiProvider.overrideWithValue(
      streamingVoiceApi ?? FakeStreamingVoiceApi(),
    ),
    streamingVoiceEnabledProvider.overrideWithValue(streamingVoiceEnabled),
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
  var captureCount = 0;

  @override
  Future<RecordedVoiceAudio?> captureUtterance({
    required VoiceCaptureConfig config,
    required SpeechStartCallback onSpeechStart,
  }) {
    captureCount++;
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

class FakeStreamingAudioCaptureService implements StreamingAudioCaptureService {
  var cancelCount = 0;
  var captureCount = 0;

  @override
  Future<void> cancel() async {
    cancelCount++;
  }

  @override
  Future<bool> streamUtterance({
    required VoiceCaptureConfig config,
    required SpeechStartCallback onSpeechStart,
    required SpeechEndCallback onSpeechEnded,
    required AudioChunkCallback onAudioChunk,
  }) async {
    captureCount++;
    onSpeechStart();
    await onAudioChunk(Uint8List.fromList([1, 2, 3]));
    onSpeechEnded();
    return true;
  }
}

class FakeBargeInDetectionService implements BargeInDetectionService {
  BargeInCallback? _onBargeIn;
  var startCount = 0;
  var stopCount = 0;

  @override
  Future<void> start({
    required VoiceCaptureConfig config,
    required BargeInCallback onBargeIn,
  }) async {
    startCount++;
    _onBargeIn = onBargeIn;
  }

  @override
  Future<void> stop() async {
    stopCount++;
  }

  void triggerBargeIn() {
    _onBargeIn?.call();
  }
}

class FakeAudioPlaybackService implements AudioPlaybackService {
  AudioPlaybackCompleteCallback? _onComplete;
  String? playedAudioBase64;
  var playCount = 0;
  var stopCount = 0;

  @override
  Future<void> playBase64Audio(
    String audioBase64, {
    required String contentType,
    required AudioPlaybackCompleteCallback onComplete,
    required AudioPlaybackErrorCallback onError,
  }) async {
    playCount++;
    playedAudioBase64 = audioBase64;
    _onComplete = onComplete;
  }

  @override
  Future<void> pause() async {}

  @override
  Future<void> stop() async {
    stopCount++;
  }

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
  final receivedConversationIds = <String?>[];
  Completer<CloudVoiceTurnResponse>? _heldResponse;

  @override
  Future<CloudVoiceTurnResponse> sendVoiceTurn({
    required XFile audio,
    required String inputMimeType,
    String? conversationId,
  }) async {
    receivedConversationId = conversationId;
    receivedConversationIds.add(conversationId);
    final response = const CloudVoiceTurnResponse(
      conversationId: 'conversation-1',
      transcript: 'Hey Rex',
      responseText: 'Rex answer',
      audioContentType: 'audio/mpeg',
      audioBase64: 'bXAzLWJ5dGVz',
      audioEncoding: 'MP3',
      voiceName: 'en-US-Neural2-J',
      languageCode: 'en-US',
    );
    final heldResponse = _heldResponse;
    if (heldResponse != null) {
      return heldResponse.future;
    }
    return response;
  }

  void holdNextResponse() {
    _heldResponse = Completer<CloudVoiceTurnResponse>();
  }

  void releaseHeldResponse() {
    final heldResponse = _heldResponse;
    if (heldResponse == null || heldResponse.isCompleted) {
      return;
    }
    heldResponse.complete(
      const CloudVoiceTurnResponse(
        conversationId: 'conversation-1',
        transcript: 'Hey Rex',
        responseText: 'Rex answer',
        audioContentType: 'audio/mpeg',
        audioBase64: 'bXAzLWJ5dGVz',
        audioEncoding: 'MP3',
        voiceName: 'en-US-Neural2-J',
        languageCode: 'en-US',
      ),
    );
  }
}

class FakeStreamingVoiceApi extends StreamingVoiceApi {
  FakeStreamingVoiceApi({FakeStreamingVoiceSession? session})
    : session = session ?? FakeStreamingVoiceSession(),
      super(connector: (_) async => FakeVoiceWebSocket());

  final FakeStreamingVoiceSession session;
  final sessions = <FakeStreamingVoiceSession>[];
  var connectCount = 0;
  String? receivedConversationId;

  @override
  Future<StreamingVoiceSession> connect({
    String? conversationId,
    String inputMimeType = 'audio/linear16',
    int sampleRate = 16000,
  }) async {
    connectCount++;
    receivedConversationId = conversationId;
    if (connectCount == 1) {
      sessions.add(session);
      return session;
    }
    final nextSession = FakeStreamingVoiceSession();
    sessions.add(nextSession);
    return nextSession;
  }
}

class FakeStreamingVoiceSession extends StreamingVoiceSession {
  FakeStreamingVoiceSession() : super(FakeVoiceWebSocket());

  final sentAudioChunks = <List<int>>[];
  final _controller = StreamController<VoiceStreamEvent>();
  var utteranceEnded = false;
  var utteranceEndCount = 0;
  var sessionEnded = false;
  var interruptCount = 0;

  @override
  Stream<VoiceStreamEvent> get events => _controller.stream;

  @override
  void sendAudioChunk(Uint8List chunk) {
    sentAudioChunks.add(chunk.toList(growable: false));
  }

  @override
  void endUtterance() {
    utteranceEnded = true;
    utteranceEndCount++;
    final turnNumber = utteranceEndCount;
    final answer = turnNumber == 1
        ? 'Rex stream answer.'
        : 'Rex stream answer $turnNumber.';
    _controller
      ..add(
        const VoiceStreamEvent('transcript.final', {
          'event': 'transcript.final',
          'transcript': 'Hey Rex',
        }),
      )
      ..add(
        const VoiceStreamEvent('conversation.updated', {
          'event': 'conversation.updated',
          'conversation_id': 'conversation-1',
        }),
      )
      ..add(
        VoiceStreamEvent('assistant.token', {
          'event': 'assistant.token',
          'token': turnNumber == 1 ? 'Rex stream ' : 'Rex stream answer ',
        }),
      )
      ..add(
        VoiceStreamEvent('assistant.token', {
          'event': 'assistant.token',
          'token': turnNumber == 1 ? 'answer.' : '$turnNumber.',
        }),
      )
      ..add(
        VoiceStreamEvent('assistant.audio_chunk', {
          'event': 'assistant.audio_chunk',
          'audio_base64': turnNumber == 1 ? 'bXAzLWJ5dGVz' : 'bXAzLWJ5dGVzMg==',
          'audio_content_type': 'audio/mpeg',
        }),
      )
      ..add(
        VoiceStreamEvent('messages.updated', {
          'event': 'messages.updated',
          'conversation_id': 'conversation-1',
          'messages': [
            {
              'id': 'message-1',
              'conversation_id': 'conversation-1',
              'role': 'assistant',
              'content': answer,
              'timestamp': '2026-05-17T00:00:00Z',
            },
          ],
        }),
      )
      ..add(
        VoiceStreamEvent('assistant.done', {
          'event': 'assistant.done',
          'conversation_id': 'conversation-1',
          'response_text': answer,
        }),
      );
  }

  @override
  void interrupt() {
    interruptCount++;
  }

  @override
  Future<void> endSession() async {
    sessionEnded = true;
    if (!_controller.isClosed) {
      await _controller.close();
    }
  }
}

class FakeVoiceWebSocket implements VoiceWebSocket {
  @override
  Stream<dynamic> get stream => const Stream<dynamic>.empty();

  @override
  void add(dynamic data) {}

  @override
  Future<void> close() async {}
}
