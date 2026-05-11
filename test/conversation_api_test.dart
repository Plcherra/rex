import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/chat/data/conversation_api.dart';
import 'package:rex/features/chat/domain/chat_message.dart';

void main() {
  test(
    'ConversationApi gets conversations with last message preview',
    () async {
      final api = ConversationApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          expect(request.method, 'GET');
          expect(request.url.toString(), 'http://rex.test/conversations');
          return http.Response('''
          [
            {
              "id": "conversation-1",
              "title": "Work stress",
              "timestamp": "2026-05-11T10:00:00Z",
              "last_message": {
                "id": "message-1",
                "conversation_id": "conversation-1",
                "role": "assistant",
                "content": "Let's be practical.",
                "timestamp": "2026-05-11T10:02:00Z"
              }
            }
          ]
          ''', 200);
        }),
      );

      final conversations = await api.getConversations();

      expect(conversations, hasLength(1));
      expect(conversations.first.id, 'conversation-1');
      expect(conversations.first.lastMessage?.content, "Let's be practical.");
    },
  );

  test('ConversationApi creates a conversation', () async {
    final api = ConversationApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.toString(), 'http://rex.test/conversations');
        return http.Response('''
          {
            "id": "conversation-new",
            "title": null,
            "timestamp": "2026-05-11T12:00:00Z",
            "last_message": null
          }
          ''', 201);
      }),
    );

    final conversation = await api.createConversation();

    expect(conversation.id, 'conversation-new');
    expect(conversation.lastMessage, isNull);
  });

  test(
    'ConversationApi gets conversation messages as domain messages',
    () async {
      final api = ConversationApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          expect(request.method, 'GET');
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
              "content": "Hello Rex",
              "timestamp": "2026-05-11T10:01:00Z"
            }
          ]
          ''', 200);
        }),
      );

      final messages = await api.getConversationMessages('conversation-1');

      expect(messages, hasLength(1));
      expect(messages.first.role, ChatMessageRole.user);
      expect(messages.first.content, 'Hello Rex');
    },
  );

  test('ConversationApi deletes a conversation', () async {
    final api = ConversationApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.method, 'DELETE');
        expect(
          request.url.toString(),
          'http://rex.test/conversations/conversation-1',
        );
        return http.Response('', 204);
      }),
    );

    await api.deleteConversation('conversation-1');
  });
}
