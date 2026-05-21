import 'package:flutter/material.dart';

import 'package:rex/features/chat/domain/chat_message.dart';

/// A single chat line: assistant (left) or user (right).
class ChatMessageBubble extends StatelessWidget {
  const ChatMessageBubble({
    super.key,
    required this.text,
    this.isUser = false,
    this.isLoading = false,
    this.isStreaming = false,
    this.memoryCandidates = const [],
    this.onApproveCandidate,
    this.onRejectCandidate,
    this.onApproveAllCandidates,
    this.onRejectAllCandidates,
    this.onEditCandidate,
  });

  final String text;
  final bool isUser;
  final bool isLoading;
  final bool isStreaming;
  final List<MemoryCandidateCard> memoryCandidates;
  final ValueChanged<MemoryCandidateCard>? onApproveCandidate;
  final ValueChanged<MemoryCandidateCard>? onRejectCandidate;
  final VoidCallback? onApproveAllCandidates;
  final VoidCallback? onRejectAllCandidates;
  final ValueChanged<MemoryCandidateCard>? onEditCandidate;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final width = MediaQuery.sizeOf(context).width;
    final maxWidth = width >= 700 ? 560.0 : width * 0.82;

    final background = isUser ? scheme.primary : scheme.surfaceContainerHigh;
    final foreground = isUser ? scheme.onPrimary : scheme.onSurface;

    return Padding(
      padding: EdgeInsets.only(
        left: isUser ? 48 : 0,
        right: isUser ? 0 : 48,
        bottom: 2,
      ),
      child: Row(
        mainAxisAlignment: isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isUser) _AssistantAvatar(color: scheme.primary),
          if (!isUser) const SizedBox(width: 8),
          Flexible(
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth),
              child: CustomPaint(
                painter: _BubbleTailPainter(color: background, isUser: isUser),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: background,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(18),
                      topRight: const Radius.circular(18),
                      bottomLeft: Radius.circular(isUser ? 18 : 6),
                      bottomRight: Radius.circular(isUser ? 6 : 18),
                    ),
                    border: Border.all(
                      color: isUser
                          ? Colors.transparent
                          : scheme.outlineVariant.withValues(alpha: 0.38),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                    child: isLoading && text.isEmpty
                        ? _TypingDots(color: foreground)
                        : Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              SelectableText.rich(
                                TextSpan(
                                  style: theme.textTheme.bodyLarge?.copyWith(
                                    color: foreground,
                                    height: 1.42,
                                  ),
                                  children: [
                                    ..._inlineMarkdownSpans(
                                      text,
                                      theme,
                                      foreground,
                                      isUser,
                                    ),
                                    if (isStreaming)
                                      WidgetSpan(
                                        alignment: PlaceholderAlignment.middle,
                                        child: _StreamingCursor(
                                          color: foreground,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                              if (!isUser && memoryCandidates.isNotEmpty) ...[
                                const SizedBox(height: 12),
                                _MemoryCandidateCards(
                                  candidates: memoryCandidates,
                                  onApprove: onApproveCandidate,
                                  onReject: onRejectCandidate,
                                  onApproveAll: onApproveAllCandidates,
                                  onRejectAll: onRejectAllCandidates,
                                  onEdit: onEditCandidate,
                                ),
                              ],
                            ],
                          ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<InlineSpan> _inlineMarkdownSpans(
    String value,
    ThemeData theme,
    Color foreground,
    bool isUser,
  ) {
    final spans = <InlineSpan>[];
    final pattern = RegExp(r'(\*\*[^*]+\*\*|`[^`]+`)');
    var cursor = 0;

    for (final match in pattern.allMatches(value)) {
      if (match.start > cursor) {
        spans.add(TextSpan(text: value.substring(cursor, match.start)));
      }

      final token = match.group(0)!;
      if (token.startsWith('**')) {
        spans.add(
          TextSpan(
            text: token.substring(2, token.length - 2),
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        );
      } else {
        spans.add(
          TextSpan(
            text: token.substring(1, token.length - 1),
            style: theme.textTheme.bodyMedium?.copyWith(
              color: foreground,
              fontFamily: 'monospace',
              backgroundColor: (isUser ? Colors.white : Colors.black)
                  .withValues(alpha: isUser ? 0.16 : 0.06),
            ),
          ),
        );
      }
      cursor = match.end;
    }

    if (cursor < value.length) {
      spans.add(TextSpan(text: value.substring(cursor)));
    }

    return spans.isEmpty ? [TextSpan(text: value)] : spans;
  }
}

class _MemoryCandidateCards extends StatelessWidget {
  const _MemoryCandidateCards({
    required this.candidates,
    this.onApprove,
    this.onReject,
    this.onApproveAll,
    this.onRejectAll,
    this.onEdit,
  });

  final List<MemoryCandidateCard> candidates;
  final ValueChanged<MemoryCandidateCard>? onApprove;
  final ValueChanged<MemoryCandidateCard>? onReject;
  final VoidCallback? onApproveAll;
  final VoidCallback? onRejectAll;
  final ValueChanged<MemoryCandidateCard>? onEdit;

  @override
  Widget build(BuildContext context) {
    final pendingCount = candidates
        .where((candidate) => candidate.isPending)
        .length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.fact_check_rounded,
              size: 16,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 6),
            Text(
              pendingCount > 0 ? 'Pending memory' : 'Memory result',
              style: Theme.of(
                context,
              ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
            const Spacer(),
            if (pendingCount > 1 && onApproveAll != null)
              TextButton.icon(
                onPressed: onApproveAll,
                icon: const Icon(Icons.done_all_rounded, size: 16),
                label: const Text('Approve all'),
              ),
            if (pendingCount > 1 && onRejectAll != null)
              TextButton.icon(
                onPressed: onRejectAll,
                icon: const Icon(Icons.delete_outline_rounded, size: 16),
                label: const Text('Reject all'),
              ),
          ],
        ),
        const SizedBox(height: 8),
        for (final candidate in candidates)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _MemoryCandidateCard(
              candidate: candidate,
              onApprove: onApprove,
              onReject: onReject,
              onEdit: onEdit,
            ),
          ),
      ],
    );
  }
}

class _MemoryCandidateCard extends StatelessWidget {
  const _MemoryCandidateCard({
    required this.candidate,
    this.onApprove,
    this.onReject,
    this.onEdit,
  });

  final MemoryCandidateCard candidate;
  final ValueChanged<MemoryCandidateCard>? onApprove;
  final ValueChanged<MemoryCandidateCard>? onReject;
  final ValueChanged<MemoryCandidateCard>? onEdit;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final isHighRisk = candidate.riskLevel == 'high';
    final verificationPassed = candidate.verificationPassed;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.78),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isHighRisk
              ? scheme.error.withValues(alpha: 0.42)
              : scheme.outlineVariant.withValues(alpha: 0.55),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _MemoryChip(label: candidate.candidateType),
                _MemoryChip(
                  label: candidate.riskLevel,
                  color: isHighRisk ? scheme.error : scheme.primary,
                ),
                _MemoryChip(label: candidate.status),
                if (verificationPassed != null)
                  _MemoryChip(
                    label: verificationPassed ? 'verified' : 'failed',
                    color: verificationPassed ? scheme.primary : scheme.error,
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              candidate.preview,
              style: theme.textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.w700,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              candidate.expectedAction,
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
                height: 1.3,
              ),
            ),
            if (candidate.verificationMessage != null) ...[
              const SizedBox(height: 6),
              Text(
                candidate.verificationMessage!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: verificationPassed == false
                      ? scheme.error
                      : scheme.onSurfaceVariant,
                  height: 1.3,
                ),
              ),
            ],
            if (candidate.canApprove || candidate.canReject) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (candidate.canApprove && onApprove != null)
                    FilledButton.icon(
                      onPressed: () => onApprove!(candidate),
                      icon: const Icon(Icons.check_rounded, size: 16),
                      label: Text(isHighRisk ? 'Confirm' : 'Approve'),
                    ),
                  if (candidate.canReject && onReject != null)
                    OutlinedButton.icon(
                      onPressed: () => onReject!(candidate),
                      icon: const Icon(Icons.close_rounded, size: 16),
                      label: const Text('Reject'),
                    ),
                  if (candidate.canApprove && onEdit != null)
                    TextButton.icon(
                      onPressed: () => onEdit!(candidate),
                      icon: const Icon(Icons.edit_rounded, size: 16),
                      label: const Text('Edit'),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _MemoryChip extends StatelessWidget {
  const _MemoryChip({required this.label, this.color});

  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final chipColor = color ?? scheme.onSurfaceVariant;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: chipColor.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: chipColor,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _AssistantAvatar extends StatelessWidget {
  const _AssistantAvatar({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return CircleAvatar(
      radius: 14,
      backgroundColor: color.withValues(alpha: 0.14),
      foregroundColor: scheme.primary,
      child: const Icon(Icons.auto_awesome_rounded, size: 15),
    );
  }
}

class _TypingDots extends StatefulWidget {
  const _TypingDots({required this.color});

  final Color color;

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (index) {
            final phase = (_controller.value + (index * 0.22)) % 1;
            final opacity = phase < 0.5 ? 0.35 + phase : 1.35 - phase;
            return Container(
              width: 6,
              height: 6,
              margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: BoxDecoration(
                color: widget.color.withValues(alpha: opacity.clamp(0.35, 1)),
                shape: BoxShape.circle,
              ),
            );
          }),
        );
      },
    );
  }
}

class _StreamingCursor extends StatefulWidget {
  const _StreamingCursor({required this.color});

  final Color color;

  @override
  State<_StreamingCursor> createState() => _StreamingCursorState();
}

class _StreamingCursorState extends State<_StreamingCursor>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 650),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(begin: 0.25, end: 1).animate(_controller),
      child: Container(
        width: 3,
        height: 18,
        margin: const EdgeInsets.only(left: 3),
        decoration: BoxDecoration(
          color: widget.color.withValues(alpha: 0.9),
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}

class _BubbleTailPainter extends CustomPainter {
  const _BubbleTailPainter({required this.color, required this.isUser});

  final Color color;
  final bool isUser;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    final path = Path();
    if (isUser) {
      path
        ..moveTo(size.width - 1, size.height - 12)
        ..lineTo(size.width + 7, size.height - 5)
        ..lineTo(size.width - 1, size.height - 2);
    } else {
      path
        ..moveTo(1, size.height - 12)
        ..lineTo(-7, size.height - 5)
        ..lineTo(1, size.height - 2);
    }
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _BubbleTailPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.isUser != isUser;
  }
}
