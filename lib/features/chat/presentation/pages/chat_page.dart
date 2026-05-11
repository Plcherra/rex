import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/core/providers.dart';
import 'package:rex/features/chat/domain/chat_message.dart';
import 'package:rex/features/chat/presentation/pages/conversation_list_page.dart';
import 'package:rex/features/chat/presentation/widgets/chat_input_bar.dart';
import 'package:rex/features/chat/presentation/widgets/chat_message_bubble.dart';

/// Main chat surface: empty thread UI + composer.
class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final TextEditingController _messageController = TextEditingController();

  static const String _welcomeMessage =
      "Hi — I'm Rex. Once you connect an AI backend, your conversation will appear here.";

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  void _onSendTapped() {
    final message = _messageController.text;
    _messageController.clear();
    ref.read(chatProvider.notifier).sendMessage(message);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final chat = ref.watch(chatProvider);
    final currentConversation = ref.watch(currentConversationProvider);
    final hasMessages = chat.messages.isNotEmpty;

    return Scaffold(
      appBar: AppBar(
        title: Text(currentConversation?.title ?? 'Rex'),
        actions: [
          IconButton(
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (context) => const ConversationListPage(),
                ),
              );
            },
            icon: const Icon(Icons.history_rounded),
            tooltip: 'Conversations',
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(
                parent: AlwaysScrollableScrollPhysics(),
              ),
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      Center(
                        child: Padding(
                          padding: const EdgeInsets.only(top: 32, bottom: 24),
                          child: Column(
                            children: [
                              Icon(
                                Icons.auto_awesome_rounded,
                                size: 40,
                                color: scheme.primary.withValues(alpha: 0.85),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'Your personal AI advisor',
                                textAlign: TextAlign.center,
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: -0.2,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Start a conversation below',
                                textAlign: TextAlign.center,
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: scheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      if (!hasMessages)
                        const ChatMessageBubble(text: _welcomeMessage)
                      else
                        ...chat.messages.map(
                          (message) => Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: ChatMessageBubble(
                              text: message.content,
                              isUser: message.role == ChatMessageRole.user,
                            ),
                          ),
                        ),
                      if (chat.isLoading) ...[
                        const SizedBox(height: 4),
                        const ChatMessageBubble(text: 'Thinking...'),
                      ],
                      if (chat.errorMessage != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          chat.errorMessage!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: scheme.error,
                          ),
                        ),
                      ],
                      const SizedBox(height: 24),
                    ]),
                  ),
                ),
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: const SizedBox.shrink(),
                ),
              ],
            ),
          ),
          ChatInputBar(
            controller: _messageController,
            onSend: chat.isLoading ? null : _onSendTapped,
          ),
        ],
      ),
    );
  }
}
