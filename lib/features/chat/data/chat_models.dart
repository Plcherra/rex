import 'package:freezed_annotation/freezed_annotation.dart';

import 'package:rex/features/chat/domain/chat_message.dart';

part 'chat_models.freezed.dart';
part 'chat_models.g.dart';

@freezed
abstract class ChatApiMessage with _$ChatApiMessage {
  const ChatApiMessage._();

  const factory ChatApiMessage({
    required String id,
    @JsonKey(name: 'conversation_id') required String conversationId,
    required String role,
    required String content,
    DateTime? timestamp,
  }) = _ChatApiMessage;

  factory ChatApiMessage.fromJson(Map<String, dynamic> json) =>
      _$ChatApiMessageFromJson(json);

  ChatMessage toDomain() {
    return ChatMessage(
      id: id,
      role: role == 'user' ? ChatMessageRole.user : ChatMessageRole.assistant,
      content: content,
      timestamp: timestamp,
    );
  }
}

@freezed
abstract class ChatApiResponse with _$ChatApiResponse {
  const factory ChatApiResponse({
    @JsonKey(name: 'conversation_id') required String conversationId,
    required String response,
    required List<ChatApiMessage> messages,
  }) = _ChatApiResponse;

  factory ChatApiResponse.fromJson(Map<String, dynamic> json) =>
      _$ChatApiResponseFromJson(json);
}

@freezed
abstract class Conversation with _$Conversation {
  const factory Conversation({
    required String id,
    String? title,
    DateTime? timestamp,
    @JsonKey(name: 'last_message') ChatApiMessage? lastMessage,
  }) = _Conversation;

  factory Conversation.fromJson(Map<String, dynamic> json) =>
      _$ConversationFromJson(json);
}
