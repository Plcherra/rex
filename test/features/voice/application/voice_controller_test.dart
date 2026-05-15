import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/voice/application/voice_controller.dart';
import 'package:rex/features/voice/data/speech_to_text_service.dart';
import 'package:rex/features/voice/data/text_to_speech_service.dart';
import 'package:rex/features/voice/domain/voice_state.dart';
import 'package:rex/services/chat_api.dart';

class FakeMicrophonePermissionService implements MicrophonePermissionService {
  FakeMicrophonePermissionService(this.decision);

  final MicrophonePermissionDecision decision;
  var requestCount = 0;
  var openSettingsCount = 0;

  @override
  Future<MicrophonePermissionDecision> requestMicrophonePermission() async {
    requestCount++;
    return decision;
  }

  @override
  Future<void> openSettings() async {
    openSettingsCount++;
  }
}

class FakeSpeechToTextService implements SpeechToTextService {
  FakeSpeechToTextService({this.initializeResult = true});

  final bool initializeResult;
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
    if (!initializeResult) {
      onError('Speech recognition is not available on this device.');
    }
    return initializeResult;
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

  void emitFinalTranscript(String transcript) {
    onFinalTranscript?.call(transcript);
  }

  void emitError(String message) {
    onError?.call(message);
  }
}

class FakeTextToSpeechService implements TextToSpeechService {
  FakeTextToSpeechService({this.throwOnSpeak = false});

  final bool throwOnSpeak;
  var speakCount = 0;
  var stopCount = 0;
  var pauseCount = 0;
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
    if (throwOnSpeak) {
      throw Exception('TTS failed');
    }
  }

  @override
  Future<void> stop() async {
    stopCount++;
  }

  @override
  Future<void> pause() async {
    pauseCount++;
  }

  void complete() {
    onComplete?.call();
  }

  void emitError(String message) {
    onError?.call(message);
  }
}

void main() {
  test('VoiceState exposes busy and startable phases', () {
    expect(const VoiceState().isIdle, true);
    expect(const VoiceState().isBusy, false);
    expect(const VoiceState().canStartListening, true);

    expect(const VoiceState(phase: VoicePhase.listening).isBusy, true);
    expect(const VoiceState(phase: VoicePhase.transcribing).isBusy, true);
    expect(const VoiceState(phase: VoicePhase.thinking).isBusy, true);
    expect(const VoiceState(phase: VoicePhase.speaking).isBusy, true);
    expect(const VoiceState(phase: VoicePhase.failed).isBusy, false);
    expect(
      const VoiceState(phase: VoicePhase.permissionDenied).canStartListening,
      true,
    );
  });

  test('VoiceController tracks listening and transcript state', () async {
    final permissionService = FakeMicrophonePermissionService(
      MicrophonePermissionDecision.granted,
    );
    final speechToTextService = FakeSpeechToTextService();
    final container = ProviderContainer(
      overrides: [
        microphonePermissionProvider.overrideWithValue(permissionService),
        speechToTextServiceProvider.overrideWithValue(speechToTextService),
      ],
    );
    addTearDown(container.dispose);

    final controller = container.read(voiceProvider.notifier);
    final started = await controller.startListening();
    speechToTextService.emitPartialTranscript('I ordered');
    controller.finishTranscription('I ordered DoorDash again.');

    final state = container.read(voiceProvider);
    expect(started, true);
    expect(state.phase, VoicePhase.transcribing);
    expect(state.partialTranscript, isEmpty);
    expect(state.finalTranscript, 'I ordered DoorDash again.');
    expect(state.isBusy, true);
    expect(state.errorMessage, isNull);
    expect(permissionService.requestCount, 1);
    expect(speechToTextService.initializeCount, 1);
    expect(speechToTextService.startListeningCount, 1);
  });

  test(
    'VoiceController sends final transcript through chat and speaks response',
    () async {
      final permissionService = FakeMicrophonePermissionService(
        MicrophonePermissionDecision.granted,
      );
      final speechToTextService = FakeSpeechToTextService();
      final textToSpeechService = FakeTextToSpeechService();
      final chatApi = ChatApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          expect(request.url.toString(), 'http://rex.test/chat');
          expect(request.body, contains('"message":"I need direct advice"'));
          expect(request.body, contains('"stream":true'));
          return http.Response(
            '''
event: conversation
data: {"conversation_id":"conversation-1"}

event: token
data: {"token":"Rex "}

event: token
data: {"token":"answer"}

event: done
data: {"conversation_id":"conversation-1","response":"Rex answer","messages":[]}

''',
            200,
            headers: {'Content-Type': 'text/event-stream'},
          );
        }),
      );
      final container = ProviderContainer(
        overrides: [
          microphonePermissionProvider.overrideWithValue(permissionService),
          speechToTextServiceProvider.overrideWithValue(speechToTextService),
          textToSpeechServiceProvider.overrideWithValue(textToSpeechService),
          chatApiProvider.overrideWithValue(chatApi),
        ],
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceProvider.notifier);
      final started = await controller.startListening();
      speechToTextService.emitFinalTranscript('I need direct advice');
      await pumpEventQueue(times: 20);

      final voiceState = container.read(voiceProvider);
      final chatState = container.read(chatProvider);
      expect(started, true);
      expect(chatState.conversationId, 'conversation-1');
      expect(chatState.messages.last.content, 'Rex answer');
      expect(textToSpeechService.speakCount, 1);
      expect(textToSpeechService.spokenText, 'Rex answer');
      expect(voiceState.phase, VoicePhase.speaking);
      expect(voiceState.spokenResponseText, 'Rex answer');
    },
  );

  test('VoiceController tracks thinking and speaking state', () async {
    final textToSpeechService = FakeTextToSpeechService();
    final container = ProviderContainer(
      overrides: [
        textToSpeechServiceProvider.overrideWithValue(textToSpeechService),
      ],
    );
    addTearDown(container.dispose);

    final controller = container.read(voiceProvider.notifier);
    controller.finishTranscription('Tell me the truth.');
    controller.startThinking();
    await controller.startSpeaking(
      'You are repeating the same spending pattern.',
    );

    var state = container.read(voiceProvider);
    expect(state.phase, VoicePhase.speaking);
    expect(state.finalTranscript, 'Tell me the truth.');
    expect(
      state.spokenResponseText,
      'You are repeating the same spending pattern.',
    );
    expect(state.isBusy, true);
    expect(textToSpeechService.speakCount, 1);
    expect(
      textToSpeechService.spokenText,
      'You are repeating the same spending pattern.',
    );

    textToSpeechService.complete();
    state = container.read(voiceProvider);
    expect(state.phase, VoicePhase.idle);
    expect(
      state.spokenResponseText,
      'You are repeating the same spending pattern.',
    );
    expect(state.isBusy, false);
  });

  test('VoiceController surfaces text to speech errors', () async {
    final textToSpeechService = FakeTextToSpeechService();
    final container = ProviderContainer(
      overrides: [
        textToSpeechServiceProvider.overrideWithValue(textToSpeechService),
      ],
    );
    addTearDown(container.dispose);

    final controller = container.read(voiceProvider.notifier);
    await controller.startSpeaking('Say this out loud.');
    textToSpeechService.emitError('TTS engine failed.');

    var state = container.read(voiceProvider);
    expect(state.phase, VoicePhase.failed);
    expect(state.errorMessage, 'TTS engine failed.');

    final throwingService = FakeTextToSpeechService(throwOnSpeak: true);
    final throwingContainer = ProviderContainer(
      overrides: [
        textToSpeechServiceProvider.overrideWithValue(throwingService),
      ],
    );
    addTearDown(throwingContainer.dispose);

    await throwingContainer
        .read(voiceProvider.notifier)
        .startSpeaking('This will fail.');
    state = throwingContainer.read(voiceProvider);
    expect(state.phase, VoicePhase.failed);
    expect(state.errorMessage, 'Text-to-speech playback failed.');
  });

  test('VoiceController ignores stale speech callbacks after cancel', () async {
    final permissionService = FakeMicrophonePermissionService(
      MicrophonePermissionDecision.granted,
    );
    final speechToTextService = FakeSpeechToTextService();
    final chatApi = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        fail('Cancelled voice input should not send chat requests.');
      }),
    );
    final container = ProviderContainer(
      overrides: [
        microphonePermissionProvider.overrideWithValue(permissionService),
        speechToTextServiceProvider.overrideWithValue(speechToTextService),
        chatApiProvider.overrideWithValue(chatApi),
      ],
    );
    addTearDown(container.dispose);

    final controller = container.read(voiceProvider.notifier);
    await controller.startListening();
    speechToTextService.emitPartialTranscript('Do not send this');
    await controller.cancelListening();
    speechToTextService.emitFinalTranscript('Do not send this');
    await pumpEventQueue(times: 5);

    final state = container.read(voiceProvider);
    expect(speechToTextService.cancelCount, 1);
    expect(state.phase, VoicePhase.idle);
    expect(state.partialTranscript, isEmpty);
    expect(state.finalTranscript, isEmpty);
    expect(container.read(chatProvider).messages, isEmpty);
  });

  test(
    'VoiceController cancels thinking without speaking stale response',
    () async {
      final textToSpeechService = FakeTextToSpeechService();
      final responseCompleter = Completer<http.Response>();
      final chatApi = ChatApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) => responseCompleter.future),
      );
      final container = ProviderContainer(
        overrides: [
          textToSpeechServiceProvider.overrideWithValue(textToSpeechService),
          chatApiProvider.overrideWithValue(chatApi),
        ],
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceProvider.notifier);
      controller.submitFinalTranscript('Answer this');
      await pumpEventQueue(times: 5);
      expect(container.read(voiceProvider).phase, VoicePhase.thinking);

      await controller.cancelCurrentTurn();
      responseCompleter.complete(
        http.Response(
          '''
event: conversation
data: {"conversation_id":"conversation-1"}

event: token
data: {"token":"Late "}

event: done
data: {"conversation_id":"conversation-1","response":"Late answer","messages":[]}

''',
          200,
          headers: {'Content-Type': 'text/event-stream'},
        ),
      );
      await pumpEventQueue(times: 20);

      final state = container.read(voiceProvider);
      expect(state.phase, VoicePhase.idle);
      expect(textToSpeechService.speakCount, 0);
    },
  );

  test('VoiceController can stop and pause speaking', () async {
    final textToSpeechService = FakeTextToSpeechService();
    final container = ProviderContainer(
      overrides: [
        textToSpeechServiceProvider.overrideWithValue(textToSpeechService),
      ],
    );
    addTearDown(container.dispose);

    final controller = container.read(voiceProvider.notifier);
    await controller.startSpeaking('A direct Rex response.');
    await controller.pauseSpeaking();

    var state = container.read(voiceProvider);
    expect(textToSpeechService.pauseCount, 1);
    expect(state.phase, VoicePhase.idle);

    await controller.startSpeaking('Another direct Rex response.');
    await controller.stopSpeaking();

    state = container.read(voiceProvider);
    expect(textToSpeechService.stopCount, 1);
    expect(state.phase, VoicePhase.idle);
  });

  test(
    'VoiceController ignores stale text to speech callbacks after stop',
    () async {
      final textToSpeechService = FakeTextToSpeechService();
      final container = ProviderContainer(
        overrides: [
          textToSpeechServiceProvider.overrideWithValue(textToSpeechService),
        ],
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceProvider.notifier);
      await controller.startSpeaking('Stop this answer.');
      await controller.stopSpeaking();
      textToSpeechService.emitError('Late TTS error.');
      textToSpeechService.complete();

      final state = container.read(voiceProvider);
      expect(textToSpeechService.stopCount, 1);
      expect(state.phase, VoicePhase.idle);
      expect(state.errorMessage, isNull);
      expect(state.spokenResponseText, 'Stop this answer.');
    },
  );

  test(
    'VoiceController handles failure and permission denied states',
    () async {
      final permissionService = FakeMicrophonePermissionService(
        MicrophonePermissionDecision.granted,
      );
      final speechToTextService = FakeSpeechToTextService();
      final container = ProviderContainer(
        overrides: [
          microphonePermissionProvider.overrideWithValue(permissionService),
          speechToTextServiceProvider.overrideWithValue(speechToTextService),
        ],
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceProvider.notifier);
      await controller.startListening();
      controller.updatePartialTranscript('partial');
      controller.denyPermission('Microphone permission is required.');

      var state = container.read(voiceProvider);
      expect(state.phase, VoicePhase.permissionDenied);
      expect(state.partialTranscript, isEmpty);
      expect(state.errorMessage, 'Microphone permission is required.');
      expect(state.isBusy, false);

      controller.fail('Speech recognition failed.');
      state = container.read(voiceProvider);
      expect(state.phase, VoicePhase.failed);
      expect(state.errorMessage, 'Speech recognition failed.');

      controller.reset();
      state = container.read(voiceProvider);
      expect(state.phase, VoicePhase.idle);
      expect(state.errorMessage, isNull);
      expect(state.finalTranscript, isEmpty);
      expect(state.spokenResponseText, isEmpty);
    },
  );

  test(
    'VoiceController does not start listening when permission is denied',
    () async {
      final permissionService = FakeMicrophonePermissionService(
        MicrophonePermissionDecision.denied,
      );
      final speechToTextService = FakeSpeechToTextService();
      final container = ProviderContainer(
        overrides: [
          microphonePermissionProvider.overrideWithValue(permissionService),
          speechToTextServiceProvider.overrideWithValue(speechToTextService),
        ],
      );
      addTearDown(container.dispose);

      final started = await container
          .read(voiceProvider.notifier)
          .startListening();

      final state = container.read(voiceProvider);
      expect(started, false);
      expect(state.phase, VoicePhase.permissionDenied);
      expect(state.isBusy, false);
      expect(
        state.errorMessage,
        'Microphone and speech recognition permission are required to talk to Rex.',
      );
      expect(permissionService.requestCount, 1);
      expect(speechToTextService.initializeCount, 0);
      expect(speechToTextService.startListeningCount, 0);
    },
  );

  test(
    'VoiceController shows settings guidance when permission is permanently denied',
    () async {
      final permissionService = FakeMicrophonePermissionService(
        MicrophonePermissionDecision.permanentlyDenied,
      );
      final speechToTextService = FakeSpeechToTextService();
      final container = ProviderContainer(
        overrides: [
          microphonePermissionProvider.overrideWithValue(permissionService),
          speechToTextServiceProvider.overrideWithValue(speechToTextService),
        ],
      );
      addTearDown(container.dispose);

      final started = await container
          .read(voiceProvider.notifier)
          .startListening();

      final state = container.read(voiceProvider);
      expect(started, false);
      expect(state.phase, VoicePhase.permissionDenied);
      expect(
        state.errorMessage,
        'Microphone or speech recognition permission is blocked. Enable it in Settings to talk to Rex.',
      );
      expect(speechToTextService.initializeCount, 0);

      await container.read(voiceProvider.notifier).openVoiceSettings();
      expect(permissionService.openSettingsCount, 1);
    },
  );

  test('VoiceController handles unavailable speech recognition', () async {
    final permissionService = FakeMicrophonePermissionService(
      MicrophonePermissionDecision.granted,
    );
    final speechToTextService = FakeSpeechToTextService(
      initializeResult: false,
    );
    final container = ProviderContainer(
      overrides: [
        microphonePermissionProvider.overrideWithValue(permissionService),
        speechToTextServiceProvider.overrideWithValue(speechToTextService),
      ],
    );
    addTearDown(container.dispose);

    final started = await container
        .read(voiceProvider.notifier)
        .startListening();

    final state = container.read(voiceProvider);
    expect(started, false);
    expect(state.phase, VoicePhase.failed);
    expect(
      state.errorMessage,
      'Speech recognition is not available on this device.',
    );
    expect(speechToTextService.initializeCount, 1);
    expect(speechToTextService.startListeningCount, 0);
  });

  test('VoiceController can stop and cancel listening', () async {
    final permissionService = FakeMicrophonePermissionService(
      MicrophonePermissionDecision.granted,
    );
    final speechToTextService = FakeSpeechToTextService();
    final container = ProviderContainer(
      overrides: [
        microphonePermissionProvider.overrideWithValue(permissionService),
        speechToTextServiceProvider.overrideWithValue(speechToTextService),
      ],
    );
    addTearDown(container.dispose);

    final controller = container.read(voiceProvider.notifier);
    await controller.startListening();
    await controller.stopListening();
    await controller.cancelListening();

    final state = container.read(voiceProvider);
    expect(speechToTextService.stopListeningCount, 1);
    expect(speechToTextService.cancelCount, 1);
    expect(state.phase, VoicePhase.idle);
  });

  test(
    'VoiceController shows guidance when stopped with no captured audio',
    () async {
      final permissionService = FakeMicrophonePermissionService(
        MicrophonePermissionDecision.granted,
      );
      final speechToTextService = FakeSpeechToTextService();
      final container = ProviderContainer(
        overrides: [
          microphonePermissionProvider.overrideWithValue(permissionService),
          speechToTextServiceProvider.overrideWithValue(speechToTextService),
        ],
      );
      addTearDown(container.dispose);

      final controller = container.read(voiceProvider.notifier);
      await controller.startListening();
      await controller.stopAndSubmitCurrentTranscript();

      final state = container.read(voiceProvider);
      expect(speechToTextService.stopListeningCount, 1);
      expect(state.phase, VoicePhase.failed);
      expect(state.errorMessage, contains('I did not catch any audio'));
      expect(state.errorMessage, contains('Simulator > I/O > Audio Input'));
    },
  );
}
