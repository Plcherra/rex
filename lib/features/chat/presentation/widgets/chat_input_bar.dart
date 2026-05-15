import 'package:flutter/material.dart';

import 'package:rex/features/chat/domain/chat_attachment.dart';

/// Composer row: text field, optional attachment preview, and send action.
class ChatInputBar extends StatelessWidget {
  const ChatInputBar({
    super.key,
    required this.controller,
    this.onSend,
    this.onPickAttachment,
    this.onRemoveAttachment,
    this.onStartVoice,
    this.attachmentName,
    this.attachmentSize,
    this.attachmentError,
    this.isLoading = false,
  });

  final TextEditingController controller;
  final VoidCallback? onSend;
  final VoidCallback? onPickAttachment;
  final VoidCallback? onRemoveAttachment;
  final VoidCallback? onStartVoice;
  final String? attachmentName;
  final int? attachmentSize;
  final String? attachmentError;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final hasBlockingAttachmentError = attachmentError != null;

    return Material(
      color: theme.scaffoldBackgroundColor,
      elevation: 6,
      shadowColor: scheme.shadow.withValues(alpha: 0.08),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: scheme.surface,
              borderRadius: BorderRadius.circular(26),
              border: Border.all(
                color: scheme.outlineVariant.withValues(alpha: 0.45),
              ),
              boxShadow: [
                BoxShadow(
                  color: scheme.shadow.withValues(alpha: 0.08),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (attachmentName != null || attachmentError != null)
                    _AttachmentPreview(
                      fileName: attachmentName,
                      fileSize: attachmentSize,
                      errorMessage: attachmentError,
                      onRemove: isLoading ? null : onRemoveAttachment,
                    ),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(left: 4, bottom: 4),
                        child: IconButton(
                          onPressed: isLoading ? null : onPickAttachment,
                          icon: const Icon(Icons.attach_file_rounded),
                          tooltip: 'Attach file',
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: IconButton(
                          onPressed: isLoading ? null : onStartVoice,
                          icon: const Icon(Icons.mic_none_rounded),
                          tooltip: 'Talk to Rex',
                        ),
                      ),
                      Expanded(
                        child: TextField(
                          controller: controller,
                          enabled: !isLoading,
                          minLines: 1,
                          maxLines: 5,
                          textInputAction: TextInputAction.newline,
                          decoration: InputDecoration(
                            hintText: 'Message Rex…',
                            border: InputBorder.none,
                            focusedBorder: InputBorder.none,
                            enabledBorder: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 12,
                            ),
                            hintStyle: theme.textTheme.bodyLarge?.copyWith(
                              color: scheme.onSurfaceVariant.withValues(
                                alpha: 0.7,
                              ),
                            ),
                          ),
                          style: theme.textTheme.bodyLarge,
                        ),
                      ),
                      ValueListenableBuilder<TextEditingValue>(
                        valueListenable: controller,
                        builder: (context, value, child) {
                          final hasText = value.text.trim().isNotEmpty;
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 4, right: 4),
                            child: IconButton.filled(
                              onPressed:
                                  hasText &&
                                      !isLoading &&
                                      !hasBlockingAttachmentError
                                  ? onSend
                                  : null,
                              style: IconButton.styleFrom(
                                backgroundColor: scheme.primary,
                                foregroundColor: scheme.onPrimary,
                                disabledBackgroundColor:
                                    scheme.surfaceContainerHighest,
                                disabledForegroundColor: scheme.onSurfaceVariant
                                    .withValues(alpha: 0.5),
                              ),
                              icon: isLoading
                                  ? const SizedBox.square(
                                      dimension: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : const Icon(
                                      Icons.arrow_upward_rounded,
                                      size: 22,
                                    ),
                              tooltip: 'Send',
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AttachmentPreview extends StatelessWidget {
  const _AttachmentPreview({
    required this.fileName,
    required this.fileSize,
    required this.errorMessage,
    required this.onRemove,
  });

  final String? fileName;
  final int? fileSize;
  final String? errorMessage;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final hasError = errorMessage != null;
    final title = fileName ?? 'Attachment';
    final subtitle = hasError
        ? errorMessage!
        : fileSize == null
        ? null
        : formatAttachmentSize(fileSize!);

    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: hasError ? scheme.errorContainer : scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 4, 8),
          child: Row(
            children: [
              Icon(
                hasError
                    ? Icons.error_outline_rounded
                    : Icons.description_outlined,
                color: hasError
                    ? scheme.onErrorContainer
                    : scheme.onSurfaceVariant,
                size: 20,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: hasError
                            ? scheme.onErrorContainer
                            : scheme.onSurface,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (subtitle != null)
                      Text(
                        subtitle,
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: hasError
                              ? scheme.onErrorContainer
                              : scheme.onSurfaceVariant,
                        ),
                      ),
                  ],
                ),
              ),
              IconButton(
                onPressed: onRemove,
                icon: const Icon(Icons.close_rounded),
                tooltip: 'Remove attachment',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
