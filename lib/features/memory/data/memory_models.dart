import 'package:freezed_annotation/freezed_annotation.dart';

part 'memory_models.freezed.dart';
part 'memory_models.g.dart';

enum MemoryType { fact, preference, event }

enum MemoryLayer { longTerm, people, rules, plans, commitments }

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

extension MemoryLayerLabel on MemoryLayer {
  String get label {
    switch (this) {
      case MemoryLayer.longTerm:
        return 'Notes';
      case MemoryLayer.people:
        return 'People';
      case MemoryLayer.rules:
        return 'Rules';
      case MemoryLayer.plans:
        return 'Plans';
      case MemoryLayer.commitments:
        return 'Commitments';
    }
  }
}

class PersonMemoryItem {
  const PersonMemoryItem({
    required this.id,
    required this.displayName,
    required this.relationship,
    required this.summary,
    required this.aliases,
    required this.importance,
    required this.status,
    required this.active,
  });

  factory PersonMemoryItem.fromJson(Map<String, dynamic> json) {
    return PersonMemoryItem(
      id: _string(json['id']) ?? '',
      displayName: _string(json['display_name']) ?? 'Person',
      relationship: _string(json['relationship']),
      summary: _string(json['summary']),
      aliases: _stringList(json['aliases']),
      importance: _int(json['importance']) ?? 3,
      status: _string(json['status']) ?? 'active',
      active: _bool(json['active']) ?? true,
    );
  }

  final String id;
  final String displayName;
  final String? relationship;
  final String? summary;
  final List<String> aliases;
  final int importance;
  final String status;
  final bool active;
}

class RuleMemoryItem {
  const RuleMemoryItem({
    required this.id,
    required this.ruleType,
    required this.title,
    required this.ruleText,
    required this.triggerKeywords,
    required this.priority,
    required this.status,
    required this.active,
  });

  factory RuleMemoryItem.fromJson(Map<String, dynamic> json) {
    return RuleMemoryItem(
      id: _string(json['id']) ?? '',
      ruleType: _string(json['rule_type']) ?? 'other',
      title: _string(json['title']) ?? 'Rule',
      ruleText: _string(json['rule_text']) ?? '',
      triggerKeywords: _stringList(json['trigger_keywords']),
      priority: _int(json['priority']) ?? 3,
      status: _string(json['status']) ?? 'active',
      active: _bool(json['active']) ?? true,
    );
  }

  final String id;
  final String ruleType;
  final String title;
  final String ruleText;
  final List<String> triggerKeywords;
  final int priority;
  final String status;
  final bool active;
}

class PlanMemoryItem {
  const PlanMemoryItem({
    required this.id,
    required this.planType,
    required this.title,
    required this.description,
    required this.desiredOutcome,
    required this.priority,
    required this.status,
    required this.active,
    required this.targetDate,
    required this.primaryEntityId,
  });

  factory PlanMemoryItem.fromJson(Map<String, dynamic> json) {
    return PlanMemoryItem(
      id: _string(json['id']) ?? '',
      planType: _string(json['plan_type']) ?? 'other',
      title: _string(json['title']) ?? 'Plan',
      description: _string(json['description']),
      desiredOutcome: _string(json['desired_outcome']),
      priority: _int(json['priority']) ?? 3,
      status: _string(json['status']) ?? 'active',
      active: _bool(json['active']) ?? true,
      targetDate: _dateTime(json['target_date']),
      primaryEntityId: _string(json['primary_entity_id']),
    );
  }

  final String id;
  final String planType;
  final String title;
  final String? description;
  final String? desiredOutcome;
  final int priority;
  final String status;
  final bool active;
  final DateTime? targetDate;
  final String? primaryEntityId;
}

class CommitmentMemoryItem {
  const CommitmentMemoryItem({
    required this.id,
    required this.commitmentType,
    required this.title,
    required this.commitmentText,
    required this.priority,
    required this.status,
    required this.active,
    required this.dueAt,
    required this.planId,
    required this.entityId,
  });

  factory CommitmentMemoryItem.fromJson(Map<String, dynamic> json) {
    return CommitmentMemoryItem(
      id: _string(json['id']) ?? '',
      commitmentType: _string(json['commitment_type']) ?? 'other',
      title: _string(json['title']) ?? 'Commitment',
      commitmentText: _string(json['commitment_text']) ?? '',
      priority: _int(json['priority']) ?? 3,
      status: _string(json['status']) ?? 'open',
      active: _bool(json['active']) ?? true,
      dueAt: _dateTime(json['due_at']),
      planId: _string(json['plan_id']),
      entityId: _string(json['entity_id']),
    );
  }

  final String id;
  final String commitmentType;
  final String title;
  final String commitmentText;
  final int priority;
  final String status;
  final bool active;
  final DateTime? dueAt;
  final String? planId;
  final String? entityId;
}

extension MemoryRecordLabel on String {
  String get memoryRecordLabel {
    if (isEmpty) {
      return '';
    }

    return split('_')
        .where((part) => part.isNotEmpty)
        .map((part) => part[0].toUpperCase() + part.substring(1))
        .join(' ');
  }
}

String? _string(Object? value) => value is String ? value : null;

int? _int(Object? value) {
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  return null;
}

bool? _bool(Object? value) => value is bool ? value : null;

List<String> _stringList(Object? value) {
  if (value is! List) {
    return const [];
  }
  return value.whereType<String>().toList(growable: false);
}

DateTime? _dateTime(Object? value) {
  if (value is! String || value.isEmpty) {
    return null;
  }
  return DateTime.tryParse(value);
}
