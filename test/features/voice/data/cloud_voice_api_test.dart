import 'dart:convert';
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/voice/data/cloud_voice_api.dart';

void main() {
  test('CloudVoiceApi transcribes uploaded audio', () async {
    final api = CloudVoiceApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://rex.test/voice/transcribe');
        return http.Response(
          jsonEncode({
            'transcript': 'Hey Rex',
            'confidence': 0.95,
            'duration_seconds': 1.2,
            'metadata': {'request_id': 'request-1'},
          }),
          200,
        );
      }),
    );

    final response = await api.transcribe(
      audio: XFile.fromData(Uint8List.fromList([1, 2, 3]), name: 'voice.m4a'),
      inputMimeType: 'audio/mp4',
    );

    expect(response.transcript, 'Hey Rex');
    expect(response.confidence, 0.95);
    expect(response.durationSeconds, 1.2);
    expect(response.metadata['request_id'], 'request-1');
  });

  test('CloudVoiceApi synthesizes response text', () async {
    final api = CloudVoiceApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://rex.test/voice/synthesize');
        expect(request.body, contains('"text":"Rex answer"'));
        return http.Response(
          jsonEncode({
            'audio_content_type': 'audio/mpeg',
            'audio_base64': 'bXAzLWJ5dGVz',
            'audio_encoding': 'MP3',
            'voice_name': 'en-US-Neural2-J',
            'language_code': 'en-US',
            'metadata': {'vendor': 'google_tts'},
          }),
          200,
        );
      }),
    );

    final response = await api.synthesize('Rex answer');

    expect(response.audioContentType, 'audio/mpeg');
    expect(response.audioBase64, 'bXAzLWJ5dGVz');
    expect(response.audioEncoding, 'MP3');
    expect(response.metadata['vendor'], 'google_tts');
  });

  test('CloudVoiceApi sends full voice turn', () async {
    final api = CloudVoiceApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://rex.test/voice/turn');
        return http.Response(
          jsonEncode({
            'conversation_id': 'conversation-1',
            'transcript': 'Hey Rex',
            'transcript_confidence': 0.95,
            'response_text': 'Rex answer',
            'audio_content_type': 'audio/mpeg',
            'audio_base64': 'bXAzLWJ5dGVz',
            'audio_encoding': 'MP3',
            'voice_name': 'en-US-Neural2-J',
            'language_code': 'en-US',
            'messages': [
              {
                'id': 'message-1',
                'conversation_id': 'conversation-1',
                'role': 'assistant',
                'content': 'Rex answer',
                'timestamp': '2026-05-15T22:00:00Z',
              },
            ],
            'voice_metadata': {
              'record': {'id': 'voice-turn-1'},
            },
          }),
          200,
        );
      }),
    );

    final response = await api.sendVoiceTurn(
      audio: XFile.fromData(Uint8List.fromList([1, 2, 3]), name: 'voice.m4a'),
      inputMimeType: 'audio/mp4',
      conversationId: 'conversation-1',
    );

    expect(response.conversationId, 'conversation-1');
    expect(response.transcript, 'Hey Rex');
    expect(response.responseText, 'Rex answer');
    expect(response.messages.single.content, 'Rex answer');
    expect(response.voiceMetadata['record'], isA<Map<String, dynamic>>());
  });

  test('CloudVoiceApi maps backend errors', () async {
    final api = CloudVoiceApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Voice transcription is not configured.'}),
          503,
        );
      }),
    );

    expect(
      () => api.synthesize('Rex answer'),
      throwsA(
        isA<CloudVoiceApiException>().having(
          (error) => error.message,
          'message',
          'Voice transcription is not configured.',
        ),
      ),
    );
  });
}
