import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/chat/data/chat_models.dart';
import 'package:rex/features/chat/data/conversation_api.dart';

final conversationListProvider =
    NotifierProvider<ConversationListController, ConversationListState>(
      ConversationListController.new,
    );

final currentConversationProvider = Provider<Conversation?>((ref) {
  final conversationId = ref.watch(
    chatProvider.select((state) => state.conversationId),
  );
  if (conversationId == null) {
    return null;
  }

  final conversations = ref.watch(
    conversationListProvider.select((state) => state.conversations),
  );
  for (final conversation in conversations) {
    if (conversation.id == conversationId) {
      return conversation;
    }
  }

  return null;
});

class ConversationListState {
  const ConversationListState({
    this.conversations = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  final List<Conversation> conversations;
  final bool isLoading;
  final String? errorMessage;

  ConversationListState copyWith({
    List<Conversation>? conversations,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
  }) {
    return ConversationListState(
      conversations: conversations ?? this.conversations,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}

class ConversationListController extends Notifier<ConversationListState> {
  @override
  ConversationListState build() => const ConversationListState();

  Future<void> loadConversations() async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final conversations = await ref
          .read(conversationApiProvider)
          .getConversations();
      state = state.copyWith(
        conversations: conversations,
        isLoading: false,
        clearError: true,
      );
    } on Object catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.toString());
    }
  }

  Future<Conversation?> createConversation() async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final conversation = await ref
          .read(conversationApiProvider)
          .createConversation();
      state = state.copyWith(
        conversations: List.unmodifiable([
          conversation,
          ...state.conversations,
        ]),
        isLoading: false,
        clearError: true,
      );
      return conversation;
    } on Object catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.toString());
      return null;
    }
  }

  Future<bool> deleteConversation(String conversationId) async {
    final previousConversations = state.conversations;
    final updatedConversations = previousConversations
        .where((conversation) => conversation.id != conversationId)
        .toList(growable: false);

    state = state.copyWith(
      conversations: updatedConversations,
      clearError: true,
    );

    try {
      await ref
          .read(conversationApiProvider)
          .deleteConversation(conversationId);

      if (ref.read(chatProvider).conversationId == conversationId) {
        ref.read(chatProvider.notifier).reset();
      }

      return true;
    } on Object catch (error) {
      state = state.copyWith(
        conversations: previousConversations,
        errorMessage: error.toString(),
      );
      return false;
    }
  }
}
