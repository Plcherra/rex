import 'package:freezed_annotation/freezed_annotation.dart';

part 'memory_models.freezed.dart';
part 'memory_models.g.dart';

enum MemoryType { fact, preference, event }

@freezed
abstract class MemoryItem with _$MemoryItem {
  const factory MemoryItem({
    required String id,
    @JsonKey(name: 'memory_type') required MemoryType memoryType,
    required String content,
    @JsonKey(name: 'source_conversation_id') String? sourceConversationId,
    @JsonKey(name: 'source_message_id') String? sourceMessageId,
    required int importance,
    required bool active,
    @JsonKey(name: 'created_at') DateTime? createdAt,
    @JsonKey(name: 'updated_at') DateTime? updatedAt,
    @JsonKey(name: 'last_accessed_at') DateTime? lastAccessedAt,
  }) = _MemoryItem;

  factory MemoryItem.fromJson(Map<String, dynamic> json) =>
      _$MemoryItemFromJson(json);
}

extension MemoryTypeLabel on MemoryType {
  String get label {
    switch (this) {
      case MemoryType.fact:
        return 'Facts';
      case MemoryType.preference:
        return 'Preferences';
      case MemoryType.event:
        return 'Events';
    }
  }

  String get apiValue => name;
}
