enum ChatMessageRole { user, assistant }

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.timestamp,
    this.isStreaming = false,
  });

  final String id;
  final ChatMessageRole role;
  final String content;
  final DateTime? timestamp;
  final bool isStreaming;

  bool get isUser => role == ChatMessageRole.user;

  ChatMessage copyWith({
    String? id,
    ChatMessageRole? role,
    String? content,
    DateTime? timestamp,
    bool? isStreaming,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isStreaming: isStreaming ?? this.isStreaming,
    );
  }
}
