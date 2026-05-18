import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:rex/features/voice/data/streaming_voice_api.dart';

void main() {
  test('StreamingVoiceApi opens wss stream and sends session start', () async {
    late Uri openedUri;
    final socket = FakeVoiceWebSocket();
    final api = StreamingVoiceApi(
      baseUrl: 'https://api.rexpilot.com',
      connector: (uri) async {
        openedUri = uri;
        return socket;
      },
    );

    await api.connect(
      conversationId: 'conversation-1',
      inputMimeType: 'audio/linear16',
      sampleRate: 16000,
    );

    expect(openedUri.toString(), 'wss://api.rexpilot.com/voice/stream');
    expect(socket.sentTextEvents.single, {
      'event': 'session.start',
      'conversation_id': 'conversation-1',
      'input_mime_type': 'audio/linear16',
      'sample_rate': 16000,
    });
  });

  test('StreamingVoiceSession sends audio and control events', () async {
    final socket = FakeVoiceWebSocket();
    final api = StreamingVoiceApi(
      baseUrl: 'http://rex.test/api',
      connector: (_) async => socket,
    );

    final session = await api.connect();
    session.sendAudioChunk(Uint8List.fromList([1, 2, 3]));
    session.endUtterance();
    session.interrupt();
    await session.endSession();

    expect(socket.sentBinaryEvents.single, [1, 2, 3]);
    expect(socket.sentTextEvents.map((event) => event['event']), [
      'session.start',
      'utterance.end',
      'user.interrupt',
      'session.end',
    ]);
    expect(socket.closed, true);
  });

  test('StreamingVoiceSession parses incoming voice events', () async {
    final socket = FakeVoiceWebSocket();
    final session = StreamingVoiceSession(socket);
    final events = <VoiceStreamEvent>[];
    final subscription = session.events.listen(events.add);

    socket.emitJson({
      'event': 'transcript.final',
      'transcript': 'Hey Rex',
      'conversation_id': 'conversation-1',
    });
    socket.emitJson({
      'event': 'assistant.audio_chunk',
      'audio_base64': 'bXAz',
      'audio_content_type': 'audio/mpeg',
    });
    await pumpEventQueue();

    expect(events.first.name, 'transcript.final');
    expect(events.first.transcript, 'Hey Rex');
    expect(events.first.conversationId, 'conversation-1');
    expect(events.last.name, 'assistant.audio_chunk');
    expect(events.last.audioBase64, 'bXAz');
    expect(events.last.audioContentType, 'audio/mpeg');

    await subscription.cancel();
  });

  test('StreamingVoiceSession maps backend error events', () async {
    final socket = FakeVoiceWebSocket();
    final session = StreamingVoiceSession(socket);

    expectLater(
      session.events,
      emitsError(
        isA<StreamingVoiceApiException>().having(
          (error) => error.message,
          'message',
          'Voice playback is not configured.',
        ),
      ),
    );

    socket.emitJson({
      'event': 'error',
      'detail': 'Voice playback is not configured.',
    });
  });
}

class FakeVoiceWebSocket implements VoiceWebSocket {
  final _controller = StreamController<dynamic>();
  final sentTextEvents = <Map<String, dynamic>>[];
  final sentBinaryEvents = <List<int>>[];
  var closed = false;

  @override
  Stream<dynamic> get stream => _controller.stream;

  @override
  void add(dynamic data) {
    if (data is String) {
      sentTextEvents.add(jsonDecode(data) as Map<String, dynamic>);
      return;
    }
    if (data is Uint8List) {
      sentBinaryEvents.add(data.toList(growable: false));
      return;
    }
    throw StateError('Unexpected event type: ${data.runtimeType}');
  }

  @override
  Future<void> close() async {
    closed = true;
    unawaited(_controller.close());
  }

  void emitJson(Map<String, dynamic> data) {
    _controller.add(jsonEncode(data));
  }
}
