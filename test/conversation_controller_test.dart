import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/chat/application/conversation_controller.dart';
import 'package:rex/features/chat/data/conversation_api.dart';
import 'package:rex/features/chat/domain/chat_message.dart';

void main() {
  test('ConversationListController loads conversations', () async {
    final conversationApi = ConversationApi(
      baseUrl: 'http://rex.test',
      client: MockClient((request) async {
        expect(request.url.toString(), 'http://rex.test/conversations');
        return http.Response('''
          [
            {
              "id": "conversation-1",
              "title": "Work stress",
              "timestamp": "2026-05-11T10:00:00Z",
              "last_message": null
            }
          ]
          ''', 200);
      }),
    );
    final container = ProviderContainer(
      overrides: [conversationApiProvider.overrideWithValue(conversationApi)],
    );
    addTearDown(container.dispose);

    await container.read(conversationListProvider.notifier).loadConversations();

    final state = container.read(conversationListProvider);
    expect(state.isLoading, false);
    expect(state.errorMessage, isNull);
    expect(state.conversations.single.id, 'conversation-1');
  });

  test(
    'ConversationListController creates conversation and current provider finds it',
    () async {
      final conversationApi = ConversationApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          expect(request.method, 'POST');
          expect(request.url.toString(), 'http://rex.test/conversations');
          return http.Response('''
          {
            "id": "conversation-new",
            "title": "New thread",
            "timestamp": "2026-05-11T12:00:00Z",
            "last_message": null
          }
          ''', 201);
        }),
      );
      final container = ProviderContainer(
        overrides: [conversationApiProvider.overrideWithValue(conversationApi)],
      );
      addTearDown(container.dispose);

      final conversation = await container
          .read(conversationListProvider.notifier)
          .createConversation();
      container.read(chatProvider.notifier).startConversation(conversation!.id);

      expect(container.read(chatProvider).conversationId, 'conversation-new');
      expect(container.read(currentConversationProvider)?.title, 'New thread');
    },
  );

  test(
    'ConversationListController deletes a conversation optimistically',
    () async {
      final conversationApi = ConversationApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          if (request.method == 'GET') {
            expect(request.url.toString(), 'http://rex.test/conversations');
            return http.Response('''
          [
            {
              "id": "conversation-1",
              "title": "Work stress",
              "timestamp": "2026-05-11T10:00:00Z",
              "last_message": null
            }
          ]
          ''', 200);
          }

          expect(request.method, 'DELETE');
          expect(
            request.url.toString(),
            'http://rex.test/conversations/conversation-1',
          );
          return http.Response('', 204);
        }),
      );
      final container = ProviderContainer(
        overrides: [conversationApiProvider.overrideWithValue(conversationApi)],
      );
      addTearDown(container.dispose);

      await container
          .read(conversationListProvider.notifier)
          .loadConversations();
      final deleted = await container
          .read(conversationListProvider.notifier)
          .deleteConversation('conversation-1');

      final state = container.read(conversationListProvider);
      expect(deleted, true);
      expect(state.errorMessage, isNull);
      expect(state.conversations, isEmpty);
    },
  );

  test(
    'ConversationListController resets chat when deleting current conversation',
    () async {
      final conversationApi = ConversationApi(
        baseUrl: 'http://rex.test',
        client: MockClient((request) async {
          if (request.method == 'GET') {
            return http.Response('''
          [
            {
              "id": "conversation-1",
              "title": "Work stress",
              "timestamp": "2026-05-11T10:00:00Z",
              "last_message": null
            }
          ]
          ''', 200);
          }

          expect(request.method, 'DELETE');
          return http.Response('', 204);
        }),
      );
      final container = ProviderContainer(
        overrides: [conversationApiProvider.overrideWithValue(conversationApi)],
      );
      addTearDown(container.dispose);

      await container
          .read(conversationListProvider.notifier)
          .loadConversations();
      container.read(chatProvider.notifier)
        ..startConversation('conversation-1')
        ..addMessage(
          const ChatMessage(
            id: 'message-1',
            role: ChatMessageRole.user,
            content: 'Delete this thread',
          ),
        );

      final deleted = await container
          .read(conversationListProvider.notifier)
          .deleteConversation('conversation-1');

      final chatState = container.read(chatProvider);
      expect(deleted, true);
      expect(chatState.conversationId, isNull);
      expect(chatState.messages, isEmpty);
    },
  );
}
