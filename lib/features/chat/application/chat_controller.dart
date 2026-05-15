import 'package:cross_file/cross_file.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/chat/data/conversation_api.dart';
import 'package:rex/features/chat/data/chat_models.dart';
import 'package:rex/features/chat/domain/chat_attachment.dart';
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
  int _streamGeneration = 0;

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
    _streamGeneration++;
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

  void cancelStreaming() {
    _streamGeneration++;
    state = state.copyWith(
      isLoading: false,
      messages: _messagesWithStreamingStopped(state.messages),
    );
  }

  Future<bool> sendMessage(
    String content, {
    XFile? attachment,
    bool stream = true,
  }) async {
    final response = await sendMessageForAssistantResponse(
      content,
      attachment: attachment,
      stream: stream,
    );
    return response != null;
  }

  Future<String?> sendMessageForAssistantResponse(
    String content, {
    XFile? attachment,
    bool stream = true,
  }) async {
    final message = content.trim();
    if (message.isEmpty || state.isLoading) {
      return null;
    }

    if (attachment != null) {
      final attachmentError = await validateChatAttachmentFile(attachment);
      if (attachmentError != null) {
        state = state.copyWith(errorMessage: attachmentError, isLoading: false);
        return null;
      }
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

    if (stream) {
      return _sendStreamingMessage(message, attachment: attachment);
    }

    return _sendNonStreamingMessageForResponse(message, attachment: attachment);
  }

  Future<String?> _sendNonStreamingMessageForResponse(
    String message, {
    XFile? attachment,
  }) async {
    try {
      final api = ref.read(chatApiProvider);
      final result = await api.sendMessage(
        message,
        conversationId: state.conversationId,
        attachment: attachment,
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
      return _assistantTextFromApiResponse(result) ?? _latestAssistantContent();
    } on ChatApiException catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.message);
      return null;
    } on Object catch (error) {
      state = state.copyWith(isLoading: false, errorMessage: error.toString());
      return null;
    }
  }

  Future<String?> _sendStreamingMessage(
    String message, {
    XFile? attachment,
  }) async {
    final generation = ++_streamGeneration;
    final streamedAssistantId =
        'local-assistant-${DateTime.now().microsecondsSinceEpoch}';

    try {
      final api = ref.read(chatApiProvider);
      await for (final event in api.streamMessage(
        message,
        conversationId: state.conversationId,
        attachment: attachment,
      )) {
        if (generation != _streamGeneration) {
          return null;
        }

        if (event is ChatStreamConversation) {
          state = state.copyWith(conversationId: event.conversationId);
        } else if (event is ChatStreamToken) {
          if (event.token.isEmpty) {
            continue;
          }
          state = state.copyWith(
            messages: _messagesWithStreamedToken(
              state.messages,
              streamedAssistantId,
              event.token,
            ),
          );
        } else if (event is ChatStreamDone) {
          final response = event.response;
          state = state.copyWith(
            conversationId: response.conversationId,
            messages: response.messages.isNotEmpty
                ? response.messages.map(_messageFromApi).toList(growable: false)
                : _messagesWithStreamingStopped(state.messages),
            isLoading: false,
            clearError: true,
          );
          return _assistantTextFromApiResponse(response) ??
              _latestAssistantContent();
        }
      }

      state = state.copyWith(
        isLoading: false,
        messages: _messagesWithStreamingStopped(state.messages),
        clearError: true,
      );
      return _latestAssistantContent();
    } on ChatApiException catch (error) {
      if (generation == _streamGeneration) {
        state = state.copyWith(
          isLoading: false,
          errorMessage: error.message,
          messages: _messagesWithStreamingStopped(state.messages),
        );
      }
      return null;
    } on Object catch (error) {
      if (generation == _streamGeneration) {
        state = state.copyWith(
          isLoading: false,
          errorMessage: error.toString(),
          messages: _messagesWithStreamingStopped(state.messages),
        );
      }
      return null;
    }
  }

  List<ChatMessage> _messagesWithStreamedToken(
    List<ChatMessage> messages,
    String assistantId,
    String token,
  ) {
    if (messages.isNotEmpty &&
        messages.last.role == ChatMessageRole.assistant &&
        messages.last.isStreaming) {
      return List.unmodifiable([
        ...messages.take(messages.length - 1),
        messages.last.copyWith(content: '${messages.last.content}$token'),
      ]);
    }

    return List.unmodifiable([
      ...messages,
      ChatMessage(
        id: assistantId,
        role: ChatMessageRole.assistant,
        content: token,
        timestamp: DateTime.now(),
        isStreaming: true,
      ),
    ]);
  }

  List<ChatMessage> _messagesWithStreamingStopped(List<ChatMessage> messages) {
    return List.unmodifiable(
      messages
          .map(
            (message) => message.isStreaming
                ? message.copyWith(isStreaming: false)
                : message,
          )
          .toList(growable: false),
    );
  }

  ChatMessage _messageFromApi(ChatApiMessage message) => message.toDomain();

  String? _assistantTextFromApiResponse(ChatApiResponse response) {
    if (response.messages.isEmpty) {
      final responseText = response.response.trim();
      return responseText.isEmpty ? null : responseText;
    }

    for (final message in response.messages.reversed) {
      if (message.role == 'assistant' && message.content.trim().isNotEmpty) {
        return message.content;
      }
    }
    return null;
  }

  String? _latestAssistantContent() {
    for (final message in state.messages.reversed) {
      if (message.role == ChatMessageRole.assistant &&
          message.content.trim().isNotEmpty) {
        return message.content;
      }
    }
    return null;
  }
}
