import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/chat/data/conversation_api.dart';
import 'package:rex/features/chat/domain/chat_message.dart';
import 'package:rex/services/chat_api.dart';

void main() {
  test('ChatController sends message and stores backend response', () async {
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://rex.test/chat');
        expect(request.body, contains('"message":"Hello Rex"'));
        return http.Response(
          '''
          {
            "conversation_id": "conversation-1",
            "response": "Rex response",
            "messages": [
              {
                "id": "message-1",
                "conversation_id": "conversation-1",
                "role": "user",
                "content": "Hello Rex",
                "timestamp": "2026-05-11T00:00:00Z"
              },
              {
                "id": "message-2",
                "conversation_id": "conversation-1",
                "role": "assistant",
                "content": "Rex response",
                "timestamp": "2026-05-11T00:00:01Z"
              }
            ]
          }
          ''',
          200,
          headers: {'Content-Type': 'application/json'},
        );
      }),
    );
    final container = ProviderContainer(
      overrides: [chatApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);

    await container
        .read(chatProvider.notifier)
        .sendMessage('Hello Rex', stream: false);

    final state = container.read(chatProvider);
    expect(state.conversationId, 'conversation-1');
    expect(state.isLoading, false);
    expect(state.errorMessage, isNull);
    expect(state.messages, hasLength(2));
    expect(state.messages.first.role, ChatMessageRole.user);
    expect(state.messages.last.role, ChatMessageRole.assistant);
    expect(state.messages.last.content, 'Rex response');
  });

  test(
    'ChatController streams tokens into the active assistant message',
    () async {
      final api = ChatApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          expect(request.url.toString(), 'http://rex.test/chat');
          expect(request.body, contains('"stream":true'));
          return http.Response(
            '''
event: conversation
data: {"conversation_id":"conversation-1"}

event: token
data: {"token":"Rex "}

event: token
data: {"token":"stream"}

event: done
data: {"conversation_id":"conversation-1","response":"Rex stream","messages":[]}

''',
            200,
            headers: {'Content-Type': 'text/event-stream'},
          );
        }),
      );
      final container = ProviderContainer(
        overrides: [chatApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      final sent = await container
          .read(chatProvider.notifier)
          .sendMessage('Hello Rex');

      final state = container.read(chatProvider);
      expect(sent, true);
      expect(state.conversationId, 'conversation-1');
      expect(state.isLoading, false);
      expect(state.errorMessage, isNull);
      expect(state.messages, hasLength(2));
      expect(state.messages.first.role, ChatMessageRole.user);
      expect(state.messages.last.role, ChatMessageRole.assistant);
      expect(state.messages.last.content, 'Rex stream');
      expect(state.messages.last.isStreaming, false);
    },
  );

  test('ChatController loads an existing conversation', () async {
    final conversationApi = ConversationApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(
          request.url.toString(),
          'http://rex.test/conversations/conversation-1/messages',
        );
        return http.Response('''
          [
            {
              "id": "message-1",
              "conversation_id": "conversation-1",
              "role": "user",
              "content": "Previous message",
              "timestamp": "2026-05-11T10:00:00Z"
            }
          ]
          ''', 200);
      }),
    );
    final container = ProviderContainer(
      overrides: [conversationApiProvider.overrideWithValue(conversationApi)],
    );
    addTearDown(container.dispose);

    await container
        .read(chatProvider.notifier)
        .loadConversation('conversation-1');

    final state = container.read(chatProvider);
    expect(state.conversationId, 'conversation-1');
    expect(state.isLoading, false);
    expect(state.messages, hasLength(1));
    expect(state.messages.single.content, 'Previous message');
  });

  test('ChatController blocks invalid attachments before API call', () async {
    var called = false;
    final api = ChatApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        called = true;
        return http.Response('{}', 200);
      }),
    );
    final container = ProviderContainer(
      overrides: [chatApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);

    final sent = await container
        .read(chatProvider.notifier)
        .sendMessage(
          'Read this',
          attachment: XFile.fromData(
            Uint8List.fromList('image'.codeUnits),
            name: 'photo.png',
            path: 'photo.png',
            length: 5,
          ),
        );

    final state = container.read(chatProvider);
    expect(sent, false);
    expect(called, false);
    expect(state.messages, isEmpty);
    expect(state.errorMessage, 'Attach a .txt, .md, or .csv file.');
  });
}
