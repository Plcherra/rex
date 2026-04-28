import 'package:flutter/material.dart';

import 'package:rex/features/chat/presentation/widgets/chat_input_bar.dart';
import 'package:rex/features/chat/presentation/widgets/chat_message_bubble.dart';

/// Main chat surface: empty thread UI + composer (no backend yet).
class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final TextEditingController _messageController = TextEditingController();

  static const String _welcomeMessage =
      "Hi — I'm Rex. Once you connect an AI backend, your conversation will appear here.";

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  void _onSendTapped() {
    // Intentionally no networking or AI — clear field for a tidy empty state.
    _messageController.clear();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Rex'),
        actions: [
          IconButton(
            onPressed: () {},
            icon: const Icon(Icons.more_horiz_rounded),
            tooltip: 'More',
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
                      const ChatMessageBubble(text: _welcomeMessage),
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
            onSend: _onSendTapped,
          ),
        ],
      ),
    );
  }
}
