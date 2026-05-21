import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/core/providers.dart';
import 'package:rex/features/voice/domain/voice_call_state.dart';
import 'package:rex/features/voice/presentation/widgets/voice_call_controls.dart';

class VoiceCallPage extends ConsumerStatefulWidget {
  const VoiceCallPage({super.key, this.autoStart = true});

  final bool autoStart;

  @override
  ConsumerState<VoiceCallPage> createState() => _VoiceCallPageState();
}

class _VoiceCallPageState extends ConsumerState<VoiceCallPage> {
  var _didAutoStart = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !widget.autoStart || _didAutoStart) {
        return;
      }
      _didAutoStart = true;
      ref.read(voiceCallProvider.notifier).startCall();
    });
  }

  @override
  Widget build(BuildContext context) {
    final call = ref.watch(voiceCallProvider);
    final controller = ref.read(voiceCallProvider.notifier);

    ref.listen<VoiceCallState>(voiceCallProvider, (previous, next) {
      if (previous?.phase != VoiceCallPhase.listening &&
          next.phase == VoiceCallPhase.listening &&
          !next.isMuted) {
        SystemSound.play(SystemSoundType.click);
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Call Rex'),
        actions: [
          IconButton(
            onPressed: controller.reset,
            icon: const Icon(Icons.restart_alt_rounded),
            tooltip: 'Reset call',
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
          child: Column(
            children: [
              _CallHeader(call: call),
              const SizedBox(height: 12),
              Expanded(child: _CallConversation(call: call)),
              const SizedBox(height: 18),
              VoiceCallControls(
                state: call,
                onStart: controller.startCall,
                onEnd: () {
                  controller.endCall();
                  Navigator.of(context).maybePop();
                },
                onToggleMute: controller.toggleMuted,
                onInterrupt: () {
                  controller.interruptAndListen(reason: 'Rex was interrupted.');
                },
                onRetry: controller.startCall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CallHeader extends StatelessWidget {
  const _CallHeader({required this.call});

  final VoiceCallState call;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Row(
      children: [
        CircleAvatar(
          radius: 18,
          backgroundColor: scheme.secondaryContainer,
          foregroundColor: scheme.onSecondaryContainer,
          child: const Icon(Icons.auto_awesome_rounded, size: 18),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            'Rex',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        _CallStatusPill(call: call),
      ],
    );
  }
}

class _CallStatusPill extends StatelessWidget {
  const _CallStatusPill({required this.call});

  final VoiceCallState call;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final status = _statusText(call);
    final color = _statusColor(scheme, call);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (call.phase == VoiceCallPhase.thinking) ...[
              SizedBox.square(
                dimension: 10,
                child: CircularProgressIndicator(
                  strokeWidth: 1.8,
                  color: color,
                ),
              ),
              const SizedBox(width: 7),
            ] else ...[
              Icon(_statusIcon(call), size: 13, color: color),
              const SizedBox(width: 6),
            ],
            Text(
              status,
              style: theme.textTheme.labelMedium?.copyWith(
                color: color,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _statusText(VoiceCallState call) {
    if (call.isMuted && call.phase == VoiceCallPhase.listening) {
      return 'Muted';
    }
    return switch (call.phase) {
      VoiceCallPhase.idle => 'Ready',
      VoiceCallPhase.listening => 'Listening',
      VoiceCallPhase.thinking => 'Thinking',
      VoiceCallPhase.speaking => 'Live',
      VoiceCallPhase.failed => 'Issue',
    };
  }

  IconData _statusIcon(VoiceCallState call) {
    if (call.isMuted && call.phase == VoiceCallPhase.listening) {
      return Icons.mic_off_rounded;
    }
    return switch (call.phase) {
      VoiceCallPhase.idle => Icons.call_rounded,
      VoiceCallPhase.listening => Icons.mic_rounded,
      VoiceCallPhase.thinking => Icons.more_horiz_rounded,
      VoiceCallPhase.speaking => Icons.volume_up_rounded,
      VoiceCallPhase.failed => Icons.error_outline_rounded,
    };
  }

  Color _statusColor(ColorScheme scheme, VoiceCallState call) {
    if (call.phase == VoiceCallPhase.failed) {
      return scheme.error;
    }
    if (call.phase == VoiceCallPhase.thinking) {
      return scheme.secondary;
    }
    return scheme.primary;
  }
}

class _CallConversation extends StatelessWidget {
  const _CallConversation({required this.call});

  final VoiceCallState call;

  @override
  Widget build(BuildContext context) {
    final transcript = call.currentTranscript.trim();
    final response = call.lastAssistantResponse.trim();
    final hasTranscript = transcript.isNotEmpty;
    final hasResponse = response.isNotEmpty;
    final isThinking = call.phase == VoiceCallPhase.thinking;
    final isFailed = call.phase == VoiceCallPhase.failed;
    final hasRecoverableError =
        !isFailed && (call.errorMessage?.trim().isNotEmpty ?? false);

    return Align(
      alignment: Alignment.topCenter,
      child: SingleChildScrollView(
        padding: const EdgeInsets.only(top: 8, bottom: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (!hasTranscript && !hasResponse && !isThinking && !isFailed)
              _EmptyCallHint(call: call),
            if (hasTranscript) ...[
              _UserBubble(text: transcript),
              const SizedBox(height: 14),
            ],
            if (hasResponse)
              _RexBubble(text: response, isThinking: isThinking)
            else if (isThinking)
              const _RexThinkingBubble(),
            if (hasRecoverableError) ...[
              const SizedBox(height: 14),
              _CallError(message: call.errorMessage),
            ],
            if (isFailed) _CallError(message: call.errorMessage),
          ],
        ),
      ),
    );
  }
}

class _EmptyCallHint extends StatelessWidget {
  const _EmptyCallHint({required this.call});

  final VoiceCallState call;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final text = call.phase == VoiceCallPhase.idle
        ? 'Start a call when you are ready.'
        : 'Start talking. Your words will appear here.';

    return Padding(
      padding: const EdgeInsets.only(top: 64),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: theme.textTheme.bodyLarge?.copyWith(
          color: scheme.onSurfaceVariant,
          height: 1.35,
        ),
      ),
    );
  }
}

class _UserBubble extends StatelessWidget {
  const _UserBubble({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Align(
      alignment: Alignment.centerRight,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.86,
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: scheme.primaryContainer,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(18),
              topRight: Radius.circular(18),
              bottomLeft: Radius.circular(18),
              bottomRight: Radius.circular(4),
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Text(
              text,
              style: theme.textTheme.bodyLarge?.copyWith(
                color: scheme.onPrimaryContainer,
                height: 1.3,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _RexBubble extends StatelessWidget {
  const _RexBubble({required this.text, required this.isThinking});

  final String text;
  final bool isThinking;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _RexAvatar(isThinking: isThinking),
        const SizedBox(width: 8),
        Flexible(
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHigh,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Text(
                text,
                style: theme.textTheme.bodyLarge?.copyWith(height: 1.35),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _RexThinkingBubble extends StatelessWidget {
  const _RexThinkingBubble();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const _RexAvatar(isThinking: true),
        const SizedBox(width: 8),
        Text(
          'Rex',
          style: theme.textTheme.labelLarge?.copyWith(
            color: scheme.onSurfaceVariant,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(width: 8),
        SizedBox.square(
          dimension: 12,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: scheme.secondary,
          ),
        ),
      ],
    );
  }
}

class _RexAvatar extends StatelessWidget {
  const _RexAvatar({required this.isThinking});

  final bool isThinking;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return CircleAvatar(
      radius: 15,
      backgroundColor: scheme.secondaryContainer.withValues(alpha: 0.8),
      foregroundColor: scheme.onSecondaryContainer,
      child: isThinking
          ? SizedBox.square(
              dimension: 11,
              child: CircularProgressIndicator(
                strokeWidth: 1.8,
                color: scheme.onSecondaryContainer,
              ),
            )
          : const Icon(Icons.auto_awesome_rounded, size: 15),
    );
  }
}

class _CallError extends StatelessWidget {
  const _CallError({required this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Icon(
              Icons.error_outline_rounded,
              color: scheme.onErrorContainer,
              size: 18,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                message ?? 'Something interrupted the voice call.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: scheme.onErrorContainer,
                  height: 1.3,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
