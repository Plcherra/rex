enum ChatMessageRole { user, assistant }

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.timestamp,
  });

  final String id;
  final ChatMessageRole role;
  final String content;
  final DateTime? timestamp;

  bool get isUser => role == ChatMessageRole.user;
}
