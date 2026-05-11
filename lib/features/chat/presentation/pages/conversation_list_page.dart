import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/core/providers.dart';
import 'package:rex/features/chat/data/chat_models.dart';

class ConversationListPage extends ConsumerStatefulWidget {
  const ConversationListPage({super.key});

  @override
  ConsumerState<ConversationListPage> createState() =>
      _ConversationListPageState();
}

class _ConversationListPageState extends ConsumerState<ConversationListPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(conversationListProvider.notifier).loadConversations(),
    );
  }

  Future<void> _openConversation(Conversation conversation) async {
    await ref.read(chatProvider.notifier).loadConversation(conversation.id);
    if (!mounted) {
      return;
    }

    Navigator.of(context).pop();
  }

  Future<void> _newConversation() async {
    final conversation = await ref
        .read(conversationListProvider.notifier)
        .createConversation();
    if (conversation == null) {
      return;
    }

    ref.read(chatProvider.notifier).startConversation(conversation.id);
    if (!mounted) {
      return;
    }

    Navigator.of(context).pop();
  }

  Future<void> _deleteConversation(Conversation conversation) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete conversation?'),
        content: const Text(
          'This removes the conversation and its messages from Rex.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed != true) {
      return;
    }

    final wasCurrent = ref.read(chatProvider).conversationId == conversation.id;
    final deleted = await ref
        .read(conversationListProvider.notifier)
        .deleteConversation(conversation.id);

    if (!mounted) {
      return;
    }

    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();

    if (!deleted) {
      final errorMessage =
          ref.read(conversationListProvider).errorMessage ??
          'Could not delete conversation.';
      messenger.showSnackBar(SnackBar(content: Text(errorMessage)));
      return;
    }

    messenger.showSnackBar(
      const SnackBar(content: Text('Conversation deleted')),
    );

    if (wasCurrent) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(conversationListProvider);
    final currentConversation = ref.watch(currentConversationProvider);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Conversations'),
        actions: [
          IconButton(
            onPressed: state.isLoading ? null : _newConversation,
            icon: const Icon(Icons.add_rounded),
            tooltip: 'New conversation',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () =>
            ref.read(conversationListProvider.notifier).loadConversations(),
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            if (state.errorMessage != null)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                  child: Text(
                    state.errorMessage!,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.error,
                    ),
                  ),
                ),
              ),
            if (state.isLoading && state.conversations.isEmpty)
              const SliverFillRemaining(
                child: Center(child: CircularProgressIndicator()),
              )
            else if (state.conversations.isEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.forum_outlined,
                          color: scheme.onSurfaceVariant,
                          size: 40,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'No conversations yet',
                          style: theme.textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Start a new one when you are ready.',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: 20),
                        FilledButton.icon(
                          onPressed: state.isLoading ? null : _newConversation,
                          icon: const Icon(Icons.add_rounded),
                          label: const Text('New Conversation'),
                        ),
                      ],
                    ),
                  ),
                ),
              )
            else
              SliverList.builder(
                itemCount: state.conversations.length,
                itemBuilder: (context, index) {
                  final conversation = state.conversations[index];
                  return _ConversationTile(
                    conversation: conversation,
                    isSelected: conversation.id == currentConversation?.id,
                    onTap: () => _openConversation(conversation),
                    onDelete: () => _deleteConversation(conversation),
                  );
                },
              ),
          ],
        ),
      ),
      floatingActionButton: state.conversations.isEmpty
          ? null
          : FloatingActionButton.extended(
              onPressed: state.isLoading ? null : _newConversation,
              icon: const Icon(Icons.add_rounded),
              label: const Text('New'),
            ),
    );
  }
}

class _ConversationTile extends StatelessWidget {
  const _ConversationTile({
    required this.conversation,
    required this.isSelected,
    required this.onTap,
    required this.onDelete,
  });

  final Conversation conversation;
  final bool isSelected;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final preview = conversation.lastMessage?.content ?? 'No messages yet';

    return ListTile(
      selected: isSelected,
      selectedTileColor: scheme.primaryContainer.withValues(alpha: 0.45),
      leading: CircleAvatar(
        backgroundColor: isSelected
            ? scheme.primary
            : scheme.surfaceContainerHighest,
        foregroundColor: isSelected
            ? scheme.onPrimary
            : scheme.onSurfaceVariant,
        child: const Icon(Icons.chat_bubble_outline_rounded, size: 20),
      ),
      title: Text(
        _conversationTitle(conversation),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(preview, maxLines: 2, overflow: TextOverflow.ellipsis),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            _timestampLabel(conversation.timestamp),
            style: theme.textTheme.labelSmall?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 4),
          PopupMenuButton<_ConversationAction>(
            tooltip: 'Conversation actions',
            onSelected: (action) {
              switch (action) {
                case _ConversationAction.delete:
                  onDelete();
              }
            },
            itemBuilder: (context) => const [
              PopupMenuItem(
                value: _ConversationAction.delete,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.delete_outline_rounded),
                  title: Text('Delete'),
                ),
              ),
            ],
          ),
        ],
      ),
      onTap: onTap,
      onLongPress: onDelete,
    );
  }

  String _conversationTitle(Conversation conversation) {
    final title = conversation.title?.trim();
    if (title != null && title.isNotEmpty) {
      return title;
    }

    final preview = conversation.lastMessage?.content.trim();
    if (preview != null && preview.isNotEmpty) {
      return preview;
    }

    return 'New conversation';
  }

  String _timestampLabel(DateTime? timestamp) {
    if (timestamp == null) {
      return '';
    }

    final local = timestamp.toLocal();
    final hour = local.hour.toString().padLeft(2, '0');
    final minute = local.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}

enum _ConversationAction { delete }
