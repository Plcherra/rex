import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/chat/data/conversation_api.dart';
import 'package:rex/features/chat/data/chat_models.dart';
import 'package:rex/features/chat/domain/chat_message.dart';
import 'package:rex/services/chat_api.dart';

final chatApiProvider = Provider<ChatApi>((ref) => ChatApi());

final chatProvider = NotifierProvider<ChatController, ChatState>(
  ChatController.new,
);

class ChatState {
  const ChatState({
    this.messages = const [],
    this.isLoading = false,
    this.conversationId,
    this.errorMessage,
  });

  final List<ChatMessage> messages;
  final bool isLoading;
  final String? conversationId;
  final String? errorMessage;

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isLoading,
    String? conversationId,
    bool clearConversationId = false,
    String? errorMessage,
    bool clearError = false,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      conversationId: clearConversationId
          ? null
          : conversationId ?? this.conversationId,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}

class ChatController extends Notifier<ChatState> {
  @override
  ChatState build() => const ChatState();

  void addMessage(ChatMessage message) {
    state = state.copyWith(
      messages: List.unmodifiable([...state.messages, message]),
      clearError: true,
    );
  }

  void setConversationId(String? conversationId) {
    state = state.copyWith(
      conversationId: conversationId,
      clearConversationId: conversationId == null,
    );
  }

  void setLoading(bool isLoading) {
    state = state.copyWith(isLoading: isLoading);
  }

  void setError(String message) {
    state = state.copyWith(errorMessage: message, isLoading: false);
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }

  void reset() {
    state = const ChatState();
  }

  void startConversation(String conversationId) {
    state = ChatState(conversationId: conversationId);
  }

  Future<void> loadConversation(String conversationId) async {
    state = state.copyWith(
      conversationId: conversationId,
      isLoading: true,
      clearError: true,
    );

    try {
      final messages = await ref
          .read(conversationApiProvider)
          .getConversationMessages(conversationId);
      state = state.copyWith(
        messages: messages,
        conversationId: conversationId,
        isLoading: false,
        clearError: true,
      );
    } on Object catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.toString());
    }
  }

  Future<void> sendMessage(String content) async {
    final message = content.trim();
    if (message.isEmpty || state.isLoading) {
      return;
    }

    final userMessage = ChatMessage(
      id: 'local-user-${DateTime.now().microsecondsSinceEpoch}',
      role: ChatMessageRole.user,
      content: message,
      timestamp: DateTime.now(),
    );
    state = state.copyWith(
      messages: List.unmodifiable([...state.messages, userMessage]),
      isLoading: true,
      clearError: true,
    );

    try {
      final api = ref.read(chatApiProvider);
      final result = await api.sendMessage(
        message,
        conversationId: state.conversationId,
      );

      state = state.copyWith(
        conversationId: result.conversationId,
        messages: result.messages.isNotEmpty
            ? result.messages.map(_messageFromApi).toList(growable: false)
            : List.unmodifiable([
                ...state.messages,
                ChatMessage(
                  id: 'local-assistant-${DateTime.now().microsecondsSinceEpoch}',
                  role: ChatMessageRole.assistant,
                  content: result.response,
                  timestamp: DateTime.now(),
                ),
              ]),
        isLoading: false,
        clearError: true,
      );
    } on Object catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.toString());
    }
  }

  ChatMessage _messageFromApi(ChatApiMessage message) => message.toDomain();
}
