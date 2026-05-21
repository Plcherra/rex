// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'chat_models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_ChatApiMessage _$ChatApiMessageFromJson(Map<String, dynamic> json) =>
    _ChatApiMessage(
      id: json['id'] as String,
      conversationId: json['conversation_id'] as String,
      role: json['role'] as String,
      content: json['content'] as String,
      timestamp: json['timestamp'] == null
          ? null
          : DateTime.parse(json['timestamp'] as String),
    );

Map<String, dynamic> _$ChatApiMessageToJson(_ChatApiMessage instance) =>
    <String, dynamic>{
      'id': instance.id,
      'conversation_id': instance.conversationId,
      'role': instance.role,
      'content': instance.content,
      'timestamp': instance.timestamp?.toIso8601String(),
    };

_ChatApiResponse _$ChatApiResponseFromJson(Map<String, dynamic> json) =>
    _ChatApiResponse(
      conversationId: json['conversation_id'] as String,
      response: json['response'] as String,
      messages: (json['messages'] as List<dynamic>)
          .map((e) => ChatApiMessage.fromJson(e as Map<String, dynamic>))
          .toList(),
      memoryChanges: json['memory_changes'] as Map<String, dynamic>?,
    );

Map<String, dynamic> _$ChatApiResponseToJson(_ChatApiResponse instance) =>
    <String, dynamic>{
      'conversation_id': instance.conversationId,
      'response': instance.response,
      'messages': instance.messages,
      'memory_changes': instance.memoryChanges,
    };

_Conversation _$ConversationFromJson(Map<String, dynamic> json) =>
    _Conversation(
      id: json['id'] as String,
      title: json['title'] as String?,
      timestamp: json['timestamp'] == null
          ? null
          : DateTime.parse(json['timestamp'] as String),
      lastMessage: json['last_message'] == null
          ? null
          : ChatApiMessage.fromJson(
              json['last_message'] as Map<String, dynamic>,
            ),
    );

Map<String, dynamic> _$ConversationToJson(_Conversation instance) =>
    <String, dynamic>{
      'id': instance.id,
      'title': instance.title,
      'timestamp': instance.timestamp?.toIso8601String(),
      'last_message': instance.lastMessage,
    };
