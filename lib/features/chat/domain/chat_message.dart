enum ChatMessageRole { user, assistant }

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.timestamp,
    this.isStreaming = false,
    this.memoryCandidates = const [],
  });

  final String id;
  final ChatMessageRole role;
  final String content;
  final DateTime? timestamp;
  final bool isStreaming;
  final List<MemoryCandidateCard> memoryCandidates;

  bool get isUser => role == ChatMessageRole.user;

  ChatMessage copyWith({
    String? id,
    ChatMessageRole? role,
    String? content,
    DateTime? timestamp,
    bool? isStreaming,
    List<MemoryCandidateCard>? memoryCandidates,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isStreaming: isStreaming ?? this.isStreaming,
      memoryCandidates: memoryCandidates ?? this.memoryCandidates,
    );
  }
}

class MemoryCandidateCard {
  const MemoryCandidateCard({
    required this.id,
    required this.candidateType,
    required this.status,
    required this.riskLevel,
    required this.preview,
    required this.expectedAction,
    required this.requiresExplicitConfirmation,
    this.verificationPassed,
    this.verificationMessage,
    this.remainingConflictCount = 0,
  });

  final String id;
  final String candidateType;
  final String status;
  final String riskLevel;
  final String preview;
  final String expectedAction;
  final bool requiresExplicitConfirmation;
  final bool? verificationPassed;
  final String? verificationMessage;
  final int remainingConflictCount;

  factory MemoryCandidateCard.fromJson(Map<String, dynamic> json) {
    final verification = json['verification'];
    final verificationMap = verification is Map<String, dynamic>
        ? verification
        : const <String, dynamic>{};
    return MemoryCandidateCard(
      id: _text(json['id']),
      candidateType: _text(json['candidate_type']),
      status: _text(json['status'], fallback: 'pending'),
      riskLevel: _text(json['risk_level'], fallback: 'medium'),
      preview: _text(json['preview'], fallback: 'Pending memory change'),
      expectedAction: _text(
        json['expected_action'],
        fallback: 'Apply pending memory change after confirmation',
      ),
      requiresExplicitConfirmation:
          json['requires_explicit_confirmation'] == true,
      verificationPassed: verificationMap['passed'] is bool
          ? verificationMap['passed'] as bool
          : null,
      verificationMessage: verificationMap['message'] is String
          ? verificationMap['message'] as String
          : null,
      remainingConflictCount: verificationMap['remaining_conflict_count'] is int
          ? verificationMap['remaining_conflict_count'] as int
          : 0,
    );
  }

  bool get isPending => status == 'pending';
  bool get canApprove => isPending;
  bool get canReject => isPending;
}

String _text(Object? value, {String fallback = ''}) {
  if (value == null) {
    return fallback;
  }
  final text = value.toString().trim();
  return text.isEmpty ? fallback : text;
}
