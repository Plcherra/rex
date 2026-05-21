import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/services/chat_api.dart';

void main() {
  test('ChatApi sends multipart request when attachment is provided', () async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.toString(), 'http://rex.test/chat');
        expect(
          request.headers['content-type'],
          startsWith('multipart/form-data'),
        );
        expect(request.body, contains('name="message"'));
        expect(request.body, contains('Read this'));
        expect(request.body, contains('name="conversation_id"'));
        expect(request.body, contains('conversation-1'));
        expect(request.body, contains('name="file"'));
        expect(request.body, contains('notes.md'));
        expect(request.body, contains('Project notes'));

        return http.Response('''
          {
            "conversation_id": "conversation-1",
            "response": "Rex response",
            "messages": []
          }
          ''', 200);
      }),
    );

    final response = await api.sendMessage(
      'Read this',
      conversationId: 'conversation-1',
      attachment: XFile.fromData(
        Uint8List.fromList('Project notes'.codeUnits),
        name: 'notes.md',
        length: 'Project notes'.length,
        path: 'notes.md',
      ),
    );

    expect(response.conversationId, 'conversation-1');
    expect(response.response, 'Rex response');
  });

  test('ChatApi surfaces backend validation detail', () async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        return http.Response(
          '{"detail":"Uploaded file must be valid UTF-8 text."}',
          400,
        );
      }),
    );

    await expectLater(
      api.sendMessage(
        'Read this',
        attachment: XFile.fromData(
          Uint8List.fromList('bad'.codeUnits),
          name: 'notes.txt',
          path: 'notes.txt',
          length: 3,
        ),
      ),
      throwsA(
        isA<ChatApiException>()
            .having(
              (error) => error.message,
              'message',
              'Uploaded file must be valid UTF-8 text.',
            )
            .having(
              (error) => error.type,
              'type',
              ChatApiErrorType.backendValidation,
            ),
      ),
    );
  });

  test('ChatApi classifies upload network failures', () async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        throw http.ClientException('offline');
      }),
    );

    await expectLater(
      api.sendMessage(
        'Read this',
        attachment: XFile.fromData(
          Uint8List.fromList('notes'.codeUnits),
          name: 'notes.md',
          path: 'notes.md',
          length: 5,
        ),
      ),
      throwsA(
        isA<ChatApiException>()
            .having(
              (error) => error.message,
              'message',
              'Could not upload the file. Check your connection and try again.',
            )
            .having((error) => error.type, 'type', ChatApiErrorType.upload),
      ),
    );
  });

  test('ChatApi parses streamed SSE response events', () async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.toString(), 'http://rex.test/chat');
        expect(request.body, contains('"stream":true'));
        return http.Response(
          '''
event: conversation
data: {"conversation_id":"conversation-1"}

event: token
data: {"token":"Rex "}

event: token
data: {"token":"response"}

event: done
data: {"conversation_id":"conversation-1","response":"Rex response","messages":[]}

''',
          200,
          headers: {'Content-Type': 'text/event-stream'},
        );
      }),
    );

    final events = await api.streamMessage('Hello Rex').toList();

    expect(events, hasLength(4));
    expect(
      (events[0] as ChatStreamConversation).conversationId,
      'conversation-1',
    );
    expect((events[1] as ChatStreamToken).token, 'Rex ');
    expect((events[2] as ChatStreamToken).token, 'response');
    expect((events[3] as ChatStreamDone).response.response, 'Rex response');
  });

  test('ChatApi surfaces streamed backend error event', () async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        return http.Response(
          '''
event: error
data: {"detail":"Grok API returned an error."}

''',
          200,
          headers: {'Content-Type': 'text/event-stream'},
        );
      }),
    );

    await expectLater(
      api.streamMessage('Hello Rex').toList(),
      throwsA(
        isA<ChatApiException>().having(
          (error) => error.message,
          'message',
          'Grok API returned an error.',
        ),
      ),
    );
  });

  test('ChatApi parses memory candidate changes from response', () async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        return http.Response('''
          {
            "conversation_id": "conversation-1",
            "response": "Please confirm this memory change.",
            "messages": [],
            "memory_changes": {
              "confirmation_required": 1,
              "pending_candidates": [
                {
                  "id": "candidate-1",
                  "candidate_type": "correction",
                  "status": "pending",
                  "risk_level": "high",
                  "preview": "correction: Stephanie was not fired.",
                  "expected_action": "Apply correction and verify stale facts are gone",
                  "requires_explicit_confirmation": true
                }
              ]
            }
          }
          ''', 200);
      }),
    );

    final response = await api.sendMessage('Fix Stephanie');

    expect(response.memoryChanges?['confirmation_required'], 1);
    final candidates = response.memoryChanges?['pending_candidates'] as List;
    expect(candidates.single['id'], 'candidate-1');
  });
}
