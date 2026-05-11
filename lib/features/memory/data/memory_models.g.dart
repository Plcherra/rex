// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'memory_models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_MemoryItem _$MemoryItemFromJson(Map<String, dynamic> json) => _MemoryItem(
  id: json['id'] as String,
  memoryType: $enumDecode(_$MemoryTypeEnumMap, json['memory_type']),
  content: json['content'] as String,
  sourceConversationId: json['source_conversation_id'] as String?,
  sourceMessageId: json['source_message_id'] as String?,
  importance: (json['importance'] as num).toInt(),
  active: json['active'] as bool,
  createdAt: json['created_at'] == null
      ? null
      : DateTime.parse(json['created_at'] as String),
  updatedAt: json['updated_at'] == null
      ? null
      : DateTime.parse(json['updated_at'] as String),
  lastAccessedAt: json['last_accessed_at'] == null
      ? null
      : DateTime.parse(json['last_accessed_at'] as String),
);

Map<String, dynamic> _$MemoryItemToJson(_MemoryItem instance) =>
    <String, dynamic>{
      'id': instance.id,
      'memory_type': _$MemoryTypeEnumMap[instance.memoryType]!,
      'content': instance.content,
      'source_conversation_id': instance.sourceConversationId,
      'source_message_id': instance.sourceMessageId,
      'importance': instance.importance,
      'active': instance.active,
      'created_at': instance.createdAt?.toIso8601String(),
      'updated_at': instance.updatedAt?.toIso8601String(),
      'last_accessed_at': instance.lastAccessedAt?.toIso8601String(),
    };

const _$MemoryTypeEnumMap = {
  MemoryType.fact: 'fact',
  MemoryType.preference: 'preference',
  MemoryType.event: 'event',
};
