enum AccountabilitySignalType {
  ruleViolation,
  missedCommitment,
  planDrift,
  repeatedPattern,
  upcomingDeadline,
  budgetRisk,
  positiveFollowThrough,
  unknown,
}

enum AccountabilitySeverity { info, low, medium, high, critical, unknown }

enum AccountabilityStatus { active, dismissed, resolved, archived, unknown }

enum AccountabilitySourceType {
  personalRule,
  commitment,
  plan,
  planMilestone,
  entity,
  entityEvent,
  longTermMemory,
  message,
  conversation,
  system,
  unknown,
}

class AccountabilityOverview {
  const AccountabilityOverview({
    required this.signals,
    required this.ruleRisks,
    required this.planRisks,
    required this.recentPatterns,
    required this.activeRules,
    required this.openCommitments,
    required this.activePlans,
    required this.openMilestones,
    required this.completedMilestones,
    required this.planHierarchy,
    required this.pendingMemoryCandidates,
    required this.duplicateWarnings,
    required this.metadata,
  });

  factory AccountabilityOverview.fromJson(Map<String, dynamic> json) {
    return AccountabilityOverview(
      signals: _list(json['signals'], AccountabilitySignal.fromJson),
      ruleRisks: _list(json['rule_risks'], AccountabilitySignal.fromJson),
      planRisks: _list(json['plan_risks'], AccountabilitySignal.fromJson),
      recentPatterns: _list(
        json['recent_patterns'],
        AccountabilitySignal.fromJson,
      ),
      activeRules: _list(json['active_rules'], PersonalRule.fromJson),
      openCommitments: _list(json['open_commitments'], Commitment.fromJson),
      activePlans: _list(json['active_plans'], PlanRecord.fromJson),
      openMilestones: _list(json['open_milestones'], PlanMilestone.fromJson),
      completedMilestones: _list(
        json['completed_milestones'],
        PlanMilestone.fromJson,
      ),
      planHierarchy: _list(json['plan_hierarchy'], PlanHierarchyItem.fromJson),
      pendingMemoryCandidates: _list(
        json['pending_memory_candidates'],
        PendingMemoryCandidate.fromJson,
      ),
      duplicateWarnings: _list(
        json['duplicate_warnings'],
        DuplicateWarning.fromJson,
      ),
      metadata: _map(json['metadata']),
    );
  }

  final List<AccountabilitySignal> signals;
  final List<AccountabilitySignal> ruleRisks;
  final List<AccountabilitySignal> planRisks;
  final List<AccountabilitySignal> recentPatterns;
  final List<PersonalRule> activeRules;
  final List<Commitment> openCommitments;
  final List<PlanRecord> activePlans;
  final List<PlanMilestone> openMilestones;
  final List<PlanMilestone> completedMilestones;
  final List<PlanHierarchyItem> planHierarchy;
  final List<PendingMemoryCandidate> pendingMemoryCandidates;
  final List<DuplicateWarning> duplicateWarnings;
  final Map<String, dynamic> metadata;

  bool get isEmpty =>
      signals.isEmpty &&
      activeRules.isEmpty &&
      openCommitments.isEmpty &&
      activePlans.isEmpty &&
      openMilestones.isEmpty &&
      completedMilestones.isEmpty &&
      planHierarchy.isEmpty &&
      pendingMemoryCandidates.isEmpty &&
      duplicateWarnings.isEmpty;

  int get activePlanCount =>
      _int(metadata['active_plan_count']) ?? activePlans.length;

  int get openMilestoneCount =>
      _int(metadata['open_milestone_count']) ?? openMilestones.length;

  int get completedMilestoneCount =>
      _int(metadata['completed_milestone_count']) ?? completedMilestones.length;

  int get openTaskCount =>
      _int(metadata['open_task_count']) ?? openCommitments.length;

  int get pendingMemoryCandidateCount =>
      _int(metadata['pending_memory_candidate_count']) ??
      pendingMemoryCandidates.length;
}

class AccountabilitySignal {
  const AccountabilitySignal({
    required this.id,
    required this.signalType,
    required this.title,
    required this.summary,
    required this.reason,
    required this.severity,
    required this.confidence,
    required this.status,
    required this.sourceRefs,
    required this.suggestedPrompt,
    required this.recommendedAction,
    required this.metadata,
    required this.createdAt,
  });

  factory AccountabilitySignal.fromJson(Map<String, dynamic> json) {
    return AccountabilitySignal(
      id: _string(json['id']),
      signalType: _signalType(json['signal_type']),
      title: _string(json['title']) ?? 'Accountability signal',
      summary: _string(json['summary']) ?? '',
      reason: _string(json['reason']) ?? '',
      severity: _severity(json['severity']),
      confidence: _double(json['confidence']) ?? 0,
      status: _status(json['status']),
      sourceRefs: _list(json['source_refs'], AccountabilitySourceRef.fromJson),
      suggestedPrompt: _string(json['suggested_prompt']),
      recommendedAction: _string(json['recommended_action']),
      metadata: _map(json['metadata']),
      createdAt: _dateTime(json['created_at']),
    );
  }

  final String? id;
  final AccountabilitySignalType signalType;
  final String title;
  final String summary;
  final String reason;
  final AccountabilitySeverity severity;
  final double confidence;
  final AccountabilityStatus status;
  final List<AccountabilitySourceRef> sourceRefs;
  final String? suggestedPrompt;
  final String? recommendedAction;
  final Map<String, dynamic> metadata;
  final DateTime? createdAt;
}

class AccountabilitySourceRef {
  const AccountabilitySourceRef({
    required this.sourceType,
    required this.sourceId,
    required this.title,
    required this.excerpt,
    required this.metadata,
  });

  factory AccountabilitySourceRef.fromJson(Map<String, dynamic> json) {
    return AccountabilitySourceRef(
      sourceType: _sourceType(json['source_type']),
      sourceId: _string(json['source_id']),
      title: _string(json['title']),
      excerpt: _string(json['excerpt']),
      metadata: _map(json['metadata']),
    );
  }

  final AccountabilitySourceType sourceType;
  final String? sourceId;
  final String? title;
  final String? excerpt;
  final Map<String, dynamic> metadata;
}

class PersonalRule {
  const PersonalRule({
    required this.id,
    required this.ruleType,
    required this.title,
    required this.ruleText,
    required this.triggerKeywords,
    required this.enforcementStyle,
    required this.priority,
    required this.status,
    required this.active,
    required this.startsAt,
    required this.endsAt,
  });

  factory PersonalRule.fromJson(Map<String, dynamic> json) {
    return PersonalRule(
      id: _string(json['id']) ?? '',
      ruleType: _string(json['rule_type']) ?? 'other',
      title: _string(json['title']) ?? 'Personal rule',
      ruleText: _string(json['rule_text']) ?? '',
      triggerKeywords: _stringList(json['trigger_keywords']),
      enforcementStyle: _string(json['enforcement_style']) ?? 'gentle_direct',
      priority: _int(json['priority']) ?? 3,
      status: _string(json['status']) ?? 'active',
      active: _bool(json['active']) ?? true,
      startsAt: _dateTime(json['starts_at']),
      endsAt: _dateTime(json['ends_at']),
    );
  }

  final String id;
  final String ruleType;
  final String title;
  final String ruleText;
  final List<String> triggerKeywords;
  final String enforcementStyle;
  final int priority;
  final String status;
  final bool active;
  final DateTime? startsAt;
  final DateTime? endsAt;
}

class Commitment {
  const Commitment({
    required this.id,
    required this.commitmentType,
    required this.title,
    required this.commitmentText,
    required this.planId,
    required this.milestoneId,
    required this.entityId,
    required this.priority,
    required this.status,
    required this.active,
    required this.dueAt,
    required this.completedAt,
  });

  factory Commitment.fromJson(Map<String, dynamic> json) {
    return Commitment(
      id: _string(json['id']) ?? '',
      commitmentType: _string(json['commitment_type']) ?? 'other',
      title: _string(json['title']) ?? 'Commitment',
      commitmentText: _string(json['commitment_text']) ?? '',
      planId: _string(json['plan_id']),
      milestoneId: _string(json['milestone_id']),
      entityId: _string(json['entity_id']),
      priority: _int(json['priority']) ?? 3,
      status: _string(json['status']) ?? 'open',
      active: _bool(json['active']) ?? true,
      dueAt: _dateTime(json['due_at']),
      completedAt: _dateTime(json['completed_at']),
    );
  }

  final String id;
  final String commitmentType;
  final String title;
  final String commitmentText;
  final String? planId;
  final String? milestoneId;
  final String? entityId;
  final int priority;
  final String status;
  final bool active;
  final DateTime? dueAt;
  final DateTime? completedAt;
}

class PlanHierarchyItem {
  const PlanHierarchyItem({
    required this.plan,
    required this.openMilestones,
    required this.completedMilestones,
    required this.openCommitments,
    required this.counts,
  });

  factory PlanHierarchyItem.fromJson(Map<String, dynamic> json) {
    return PlanHierarchyItem(
      plan: PlanRecord.fromJson(_map(json['plan'])),
      openMilestones: _list(json['open_milestones'], PlanMilestone.fromJson),
      completedMilestones: _list(
        json['completed_milestones'],
        PlanMilestone.fromJson,
      ),
      openCommitments: _list(json['open_commitments'], Commitment.fromJson),
      counts: _map(json['counts']),
    );
  }

  final PlanRecord plan;
  final List<PlanMilestone> openMilestones;
  final List<PlanMilestone> completedMilestones;
  final List<Commitment> openCommitments;
  final Map<String, dynamic> counts;
}

class PendingMemoryCandidate {
  const PendingMemoryCandidate({
    required this.id,
    required this.candidateType,
    required this.status,
    required this.riskLevel,
    required this.preview,
    required this.reason,
  });

  factory PendingMemoryCandidate.fromJson(Map<String, dynamic> json) {
    return PendingMemoryCandidate(
      id: _string(json['id']) ?? '',
      candidateType: _string(json['candidate_type']) ?? 'memory_update',
      status: _string(json['status']) ?? 'pending',
      riskLevel: _string(json['risk_level']) ?? 'medium',
      preview:
          _string(json['preview']) ??
          _string(json['proposed_summary']) ??
          'Pending memory change',
      reason: _string(json['reason']) ?? _string(json['rationale']) ?? '',
    );
  }

  final String id;
  final String candidateType;
  final String status;
  final String riskLevel;
  final String preview;
  final String reason;
}

class DuplicateWarning {
  const DuplicateWarning({
    required this.recordType,
    required this.title,
    required this.recordIds,
    required this.reason,
  });

  factory DuplicateWarning.fromJson(Map<String, dynamic> json) {
    return DuplicateWarning(
      recordType: _string(json['record_type']) ?? 'record',
      title: _string(json['title']) ?? 'Duplicate warning',
      recordIds: _stringList(json['record_ids']),
      reason: _string(json['reason']) ?? '',
    );
  }

  final String recordType;
  final String title;
  final List<String> recordIds;
  final String reason;
}

class PlanRecord {
  const PlanRecord({
    required this.id,
    required this.planType,
    required this.title,
    required this.description,
    required this.desiredOutcome,
    required this.priority,
    required this.status,
    required this.active,
    required this.startDate,
    required this.targetDate,
    required this.completedAt,
    required this.lastReviewedAt,
  });

  factory PlanRecord.fromJson(Map<String, dynamic> json) {
    return PlanRecord(
      id: _string(json['id']) ?? '',
      planType: _string(json['plan_type']) ?? 'other',
      title: _string(json['title']) ?? 'Plan',
      description: _string(json['description']),
      desiredOutcome: _string(json['desired_outcome']),
      priority: _int(json['priority']) ?? 3,
      status: _string(json['status']) ?? 'active',
      active: _bool(json['active']) ?? true,
      startDate: _dateTime(json['start_date']),
      targetDate: _dateTime(json['target_date']),
      completedAt: _dateTime(json['completed_at']),
      lastReviewedAt: _dateTime(json['last_reviewed_at']),
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
  final DateTime? startDate;
  final DateTime? targetDate;
  final DateTime? completedAt;
  final DateTime? lastReviewedAt;
}

class PlanMilestone {
  const PlanMilestone({
    required this.id,
    required this.planId,
    required this.title,
    required this.description,
    required this.milestoneType,
    required this.targetDate,
    required this.priority,
    required this.status,
    required this.active,
    required this.completedAt,
    required this.openCommitments,
  });

  factory PlanMilestone.fromJson(Map<String, dynamic> json) {
    return PlanMilestone(
      id: _string(json['id']) ?? '',
      planId: _string(json['plan_id']) ?? '',
      title: _string(json['title']) ?? 'Milestone',
      description: _string(json['description']),
      milestoneType: _string(json['milestone_type']) ?? 'checkpoint',
      targetDate: _dateTime(json['target_date']),
      priority: _int(json['priority']) ?? 3,
      status: _string(json['status']) ?? 'open',
      active: _bool(json['active']) ?? true,
      completedAt: _dateTime(json['completed_at']),
      openCommitments: _list(json['open_commitments'], Commitment.fromJson),
    );
  }

  final String id;
  final String planId;
  final String title;
  final String? description;
  final String milestoneType;
  final DateTime? targetDate;
  final int priority;
  final String status;
  final bool active;
  final DateTime? completedAt;
  final List<Commitment> openCommitments;
}

extension AccountabilitySignalTypeLabel on AccountabilitySignalType {
  String get label {
    switch (this) {
      case AccountabilitySignalType.ruleViolation:
        return 'Rule risk';
      case AccountabilitySignalType.missedCommitment:
        return 'Missed commitment';
      case AccountabilitySignalType.planDrift:
        return 'Plan drift';
      case AccountabilitySignalType.repeatedPattern:
        return 'Pattern';
      case AccountabilitySignalType.upcomingDeadline:
        return 'Deadline';
      case AccountabilitySignalType.budgetRisk:
        return 'Budget risk';
      case AccountabilitySignalType.positiveFollowThrough:
        return 'Follow-through';
      case AccountabilitySignalType.unknown:
        return 'Signal';
    }
  }
}

extension AccountabilitySeverityLabel on AccountabilitySeverity {
  String get label {
    switch (this) {
      case AccountabilitySeverity.info:
        return 'Info';
      case AccountabilitySeverity.low:
        return 'Low';
      case AccountabilitySeverity.medium:
        return 'Medium';
      case AccountabilitySeverity.high:
        return 'High';
      case AccountabilitySeverity.critical:
        return 'Critical';
      case AccountabilitySeverity.unknown:
        return 'Unknown';
    }
  }
}

extension AccountabilityRecordLabels on String {
  String get accountabilityLabel {
    if (isEmpty) {
      return '';
    }

    return split('_')
        .where((part) => part.isNotEmpty)
        .map((part) => part[0].toUpperCase() + part.substring(1))
        .join(' ');
  }
}

List<T> _list<T>(Object? value, T Function(Map<String, dynamic>) builder) {
  if (value is! List) {
    return const [];
  }

  return value
      .whereType<Map<String, dynamic>>()
      .map(builder)
      .toList(growable: false);
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) {
    return value;
  }

  return const {};
}

List<String> _stringList(Object? value) {
  if (value is! List) {
    return const [];
  }

  return value.whereType<String>().toList(growable: false);
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

double? _double(Object? value) {
  if (value is double) {
    return value;
  }
  if (value is num) {
    return value.toDouble();
  }
  return null;
}

bool? _bool(Object? value) => value is bool ? value : null;

DateTime? _dateTime(Object? value) {
  if (value is! String || value.trim().isEmpty) {
    return null;
  }

  return DateTime.tryParse(value);
}

AccountabilitySignalType _signalType(Object? value) {
  switch (value) {
    case 'rule_violation':
      return AccountabilitySignalType.ruleViolation;
    case 'missed_commitment':
      return AccountabilitySignalType.missedCommitment;
    case 'plan_drift':
      return AccountabilitySignalType.planDrift;
    case 'repeated_pattern':
      return AccountabilitySignalType.repeatedPattern;
    case 'upcoming_deadline':
      return AccountabilitySignalType.upcomingDeadline;
    case 'budget_risk':
      return AccountabilitySignalType.budgetRisk;
    case 'positive_follow_through':
      return AccountabilitySignalType.positiveFollowThrough;
    default:
      return AccountabilitySignalType.unknown;
  }
}

AccountabilitySeverity _severity(Object? value) {
  switch (value) {
    case 'info':
      return AccountabilitySeverity.info;
    case 'low':
      return AccountabilitySeverity.low;
    case 'medium':
      return AccountabilitySeverity.medium;
    case 'high':
      return AccountabilitySeverity.high;
    case 'critical':
      return AccountabilitySeverity.critical;
    default:
      return AccountabilitySeverity.unknown;
  }
}

AccountabilityStatus _status(Object? value) {
  switch (value) {
    case 'active':
      return AccountabilityStatus.active;
    case 'dismissed':
      return AccountabilityStatus.dismissed;
    case 'resolved':
      return AccountabilityStatus.resolved;
    case 'archived':
      return AccountabilityStatus.archived;
    default:
      return AccountabilityStatus.unknown;
  }
}

AccountabilitySourceType _sourceType(Object? value) {
  switch (value) {
    case 'personal_rule':
      return AccountabilitySourceType.personalRule;
    case 'commitment':
      return AccountabilitySourceType.commitment;
    case 'plan':
      return AccountabilitySourceType.plan;
    case 'plan_milestone':
      return AccountabilitySourceType.planMilestone;
    case 'entity':
      return AccountabilitySourceType.entity;
    case 'entity_event':
      return AccountabilitySourceType.entityEvent;
    case 'long_term_memory':
      return AccountabilitySourceType.longTermMemory;
    case 'message':
      return AccountabilitySourceType.message;
    case 'conversation':
      return AccountabilitySourceType.conversation;
    case 'system':
      return AccountabilitySourceType.system;
    default:
      return AccountabilitySourceType.unknown;
  }
}
