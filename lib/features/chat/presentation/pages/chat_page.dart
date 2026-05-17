import 'package:cross_file/cross_file.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/core/providers.dart';
import 'package:rex/features/chat/application/chat_controller.dart'
    show ChatState;
import 'package:rex/features/chat/domain/chat_attachment.dart';
import 'package:rex/features/chat/domain/chat_message.dart';
import 'package:rex/features/chat/presentation/pages/conversation_list_page.dart';
import 'package:rex/features/chat/presentation/widgets/chat_input_bar.dart';
import 'package:rex/features/chat/presentation/widgets/chat_message_bubble.dart';
import 'package:rex/features/memory/presentation/pages/memory_page.dart';
import 'package:rex/features/voice/presentation/pages/voice_call_page.dart';
import 'package:rex/features/voice/presentation/widgets/voice_recorder_sheet.dart';

/// Main chat surface: empty thread UI + composer.
class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  XFile? _attachment;
  String? _attachmentName;
  int? _attachmentSize;
  String? _attachmentError;

  static const String _welcomeMessage =
      "Hi — I'm Rex. Once you connect an AI backend, your conversation will appear here.";

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    ref.listenManual<ChatState>(chatProvider, (previous, next) {
      final previousLength = previous?.messages.length ?? 0;
      final shouldScroll =
          next.messages.length != previousLength ||
          next.isLoading != (previous?.isLoading ?? false) ||
          next.errorMessage != previous?.errorMessage;
      if (shouldScroll) {
        _scrollToBottom();
      }
    });
  }

  Future<void> _onSendTapped() async {
    if (_attachmentError != null) {
      _showSnackBar(_attachmentError!);
      return;
    }

    final message = _messageController.text;
    final attachment = _attachment;
    final sent = await ref
        .read(chatProvider.notifier)
        .sendMessage(message, attachment: attachment);
    if (!mounted) {
      return;
    }

    if (sent) {
      _messageController.clear();
      setState(() {
        _attachment = null;
        _attachmentName = null;
        _attachmentSize = null;
        _attachmentError = null;
      });
      return;
    }

    final errorMessage =
        ref.read(chatProvider).errorMessage ?? 'Could not send message.';
    if (attachment != null) {
      setState(() => _attachmentError = errorMessage);
    }
    _showSnackBar(errorMessage);
  }

  Future<void> _pickAttachment() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: allowedChatAttachmentExtensions.toList(
        growable: false,
      ),
      allowMultiple: false,
      withData: true,
    );
    if (!mounted || result == null || result.files.isEmpty) {
      return;
    }

    final file = result.files.single;
    final validationError = file.bytes == null
        ? validateChatAttachment(fileName: file.name, fileSize: file.size)
        : validateChatAttachmentBytes(
            fileName: file.name,
            fileSize: file.size,
            bytes: file.bytes!,
          );
    if (validationError != null) {
      setState(() {
        _attachment = null;
        _attachmentName = file.name;
        _attachmentSize = file.size;
        _attachmentError = validationError;
      });
      _showSnackBar(validationError);
      return;
    }
    if (file.path == null && file.bytes == null) {
      setState(() {
        _attachment = null;
        _attachmentName = file.name;
        _attachmentSize = file.size;
        _attachmentError = 'Could not read selected file.';
      });
      _showSnackBar('Could not read selected file.');
      return;
    }

    final attachment = file.path != null
        ? XFile(file.path!, name: file.name, length: file.size)
        : XFile.fromData(
            file.bytes!,
            name: file.name,
            length: file.size,
            path: file.name,
          );
    setState(() {
      _attachment = attachment;
      _attachmentName = file.name;
      _attachmentSize = file.size;
      _attachmentError = null;
    });
  }

  void _removeAttachment() {
    setState(() {
      _attachment = null;
      _attachmentName = null;
      _attachmentSize = null;
      _attachmentError = null;
    });
  }

  void _showSnackBar(String message) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _openVoiceRecorder() async {
    FocusScope.of(context).unfocus();
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: false,
      builder: (context) => const VoiceRecorderSheet(),
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollController.hasClients) {
        return;
      }

      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOutCubic,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final chat = ref.watch(chatProvider);
    final currentConversation = ref.watch(currentConversationProvider);
    final hasMessages = chat.messages.isNotEmpty;
    final hasStreamingAssistant =
        hasMessages &&
        chat.messages.last.role == ChatMessageRole.assistant &&
        chat.messages.last.isStreaming;

    return Scaffold(
      appBar: AppBar(
        title: Text(currentConversation?.title ?? 'Rex'),
        actions: [
          IconButton(
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (context) => const VoiceCallPage(),
                ),
              );
            },
            icon: const Icon(Icons.call_rounded),
            tooltip: 'Call Rex',
          ),
          IconButton(
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (context) => const MemoryPage(),
                ),
              );
            },
            icon: const Icon(Icons.psychology_alt_rounded),
            tooltip: 'Memory',
          ),
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
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: Scrollbar(
                controller: _scrollController,
                child: CustomScrollView(
                  controller: _scrollController,
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  physics: const BouncingScrollPhysics(
                    parent: AlwaysScrollableScrollPhysics(),
                  ),
                  slivers: [
                    SliverPadding(
                      padding: EdgeInsets.fromLTRB(
                        16,
                        8,
                        16,
                        MediaQuery.viewInsetsOf(context).bottom > 0 ? 12 : 24,
                      ),
                      sliver: SliverList(
                        delegate: SliverChildListDelegate([
                          if (!hasMessages)
                            _EmptyChatState(
                              welcomeMessage: _welcomeMessage,
                              onPromptSelected: (prompt) {
                                _messageController.text = prompt;
                                _messageController.selection =
                                    TextSelection.collapsed(
                                      offset: prompt.length,
                                    );
                              },
                            )
                          else
                            ...chat.messages.map(
                              (message) => Padding(
                                padding: const EdgeInsets.only(bottom: 14),
                                child: ChatMessageBubble(
                                  text: message.content,
                                  isUser: message.role == ChatMessageRole.user,
                                  isStreaming: message.isStreaming,
                                ),
                              ),
                            ),
                          if (chat.isLoading && !hasStreamingAssistant) ...[
                            const SizedBox(height: 2),
                            const ChatMessageBubble(text: '', isLoading: true),
                          ],
                          if (chat.errorMessage != null) ...[
                            const SizedBox(height: 12),
                            _ChatErrorBanner(message: chat.errorMessage!),
                          ],
                          const SizedBox(height: 16),
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
            ),
            ChatInputBar(
              controller: _messageController,
              onSend: chat.isLoading || _attachmentError != null
                  ? null
                  : _onSendTapped,
              onPickAttachment: _pickAttachment,
              onRemoveAttachment: _removeAttachment,
              onStartVoice: _openVoiceRecorder,
              attachmentName: _attachmentName,
              attachmentSize: _attachmentSize,
              attachmentError: _attachmentError,
              isLoading: chat.isLoading,
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyChatState extends StatelessWidget {
  const _EmptyChatState({
    required this.welcomeMessage,
    required this.onPromptSelected,
  });

  final String welcomeMessage;
  final ValueChanged<String> onPromptSelected;

  static const _prompts = [
    'Help me think through my day.',
    'Remember that I prefer direct advice.',
    'What should I focus on next?',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.only(top: 24, bottom: 10),
      child: Column(
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              color: scheme.primary.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Icon(
                Icons.auto_awesome_rounded,
                size: 36,
                color: scheme.primary,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text(
            'Rex',
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            welcomeMessage,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: scheme.onSurfaceVariant,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 20),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 8,
            children: _prompts
                .map(
                  (prompt) => ActionChip(
                    label: Text(prompt),
                    onPressed: () => onPromptSelected(prompt),
                  ),
                )
                .toList(growable: false),
          ),
        ],
      ),
    );
  }
}

class _ChatErrorBanner extends StatelessWidget {
  const _ChatErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            Icon(
              Icons.error_outline_rounded,
              color: scheme.onErrorContainer,
              size: 18,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onErrorContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
