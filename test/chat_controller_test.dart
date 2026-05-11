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

    await container.read(chatProvider.notifier).sendMessage('Hello Rex');

    final state = container.read(chatProvider);
    expect(state.conversationId, 'conversation-1');
    expect(state.isLoading, false);
    expect(state.errorMessage, isNull);
    expect(state.messages, hasLength(2));
    expect(state.messages.first.role, ChatMessageRole.user);
    expect(state.messages.last.role, ChatMessageRole.assistant);
    expect(state.messages.last.content, 'Rex response');
  });

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
}
