import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rex/features/voice/data/native_voice_session_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('rex/native_voice');
  final binding = TestDefaultBinaryMessengerBinding.instance;

  tearDown(() {
    binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, null);
  });

  test('NativeVoiceSessionConfig serializes start payload', () {
    final config = NativeVoiceSessionConfig(
      backendBaseUrl: 'https://api.rexpilot.com',
      conversationId: 'conversation-1',
    );

    expect(config.toJson(), {
      'backendBaseUrl': 'https://api.rexpilot.com',
      'conversationId': 'conversation-1',
      'sampleRate': 16000,
      'inputMimeType': 'audio/linear16',
    });
  });

  test('NativeVoiceEvent parses common fields', () {
    final event = NativeVoiceEvent.fromMap({
      'event': 'assistant.done',
      'conversation_id': 'conversation-1',
      'response_text': 'Done.',
      'detail': 'ok',
    });

    expect(event.name, 'assistant.done');
    expect(event.conversationId, 'conversation-1');
    expect(event.responseText, 'Done.');
    expect(event.detail, 'ok');
  });

  test(
    'MethodChannelNativeVoiceSessionService invokes native commands',
    () async {
      final calls = <MethodCall>[];
      binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, (
        call,
      ) async {
        calls.add(call);
        return null;
      });
      final service = MethodChannelNativeVoiceSessionService(
        methodChannel: channel,
        eventChannel: const EventChannel('rex/native_voice_events_test'),
      );

      await service.startSession(
        const NativeVoiceSessionConfig(
          backendBaseUrl: 'https://api.rexpilot.com',
          conversationId: 'conversation-1',
        ),
      );
      await service.setMuted(true);
      await service.setForegroundState(false);
      await service.interrupt();
      await service.stopSession();

      expect(calls.map((call) => call.method), [
        'startSession',
        'setMuted',
        'setForegroundState',
        'interrupt',
        'stopSession',
      ]);
      expect(calls.first.arguments, {
        'backendBaseUrl': 'https://api.rexpilot.com',
        'conversationId': 'conversation-1',
        'sampleRate': 16000,
        'inputMimeType': 'audio/linear16',
      });
      expect(calls[1].arguments, {'isMuted': true});
      expect(calls[2].arguments, {'isForeground': false});
    },
  );

  test(
    'MethodChannelNativeVoiceSessionService tolerates missing plugin',
    () async {
      final service = MethodChannelNativeVoiceSessionService(
        methodChannel: channel,
        eventChannel: const EventChannel('rex/native_voice_events_test'),
      );

      await service.startSession(const NativeVoiceSessionConfig());
      await service.setMuted(false);
      await service.setForegroundState(true);
      await service.interrupt();
      await service.stopSession();
    },
  );
}
