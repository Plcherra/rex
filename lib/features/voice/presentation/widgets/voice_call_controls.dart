import 'package:flutter/material.dart';

import 'package:rex/features/voice/domain/voice_call_state.dart';

class VoiceCallControls extends StatelessWidget {
  const VoiceCallControls({
    super.key,
    required this.state,
    required this.onStart,
    required this.onEnd,
    required this.onToggleMute,
    required this.onInterrupt,
    required this.onRetry,
  });

  final VoiceCallState state;
  final VoidCallback onStart;
  final VoidCallback onEnd;
  final VoidCallback onToggleMute;
  final VoidCallback onInterrupt;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final canInterrupt =
        state.phase == VoiceCallPhase.speaking ||
        state.phase == VoiceCallPhase.thinking;

    if (state.phase == VoiceCallPhase.failed) {
      return Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try again'),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: OutlinedButton.icon(
              onPressed: onEnd,
              icon: const Icon(Icons.call_end_rounded),
              label: const Text('End'),
            ),
          ),
        ],
      );
    }

    if (!state.isCallActive) {
      return FilledButton.icon(
        onPressed: onStart,
        icon: const Icon(Icons.call_rounded),
        label: const Text('Start call'),
      );
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _RoundCallButton(
          tooltip: state.isMuted ? 'Unmute mic' : 'Mute mic',
          icon: state.isMuted ? Icons.mic_off_rounded : Icons.mic_rounded,
          onPressed: onToggleMute,
        ),
        const SizedBox(width: 18),
        _RoundCallButton(
          tooltip: 'End call',
          icon: Icons.call_end_rounded,
          backgroundColor: scheme.error,
          foregroundColor: scheme.onError,
          onPressed: onEnd,
          size: 70,
        ),
        const SizedBox(width: 18),
        _RoundCallButton(
          tooltip: 'Interrupt Rex',
          icon: Icons.front_hand_rounded,
          onPressed: canInterrupt ? onInterrupt : null,
          onLongPress: canInterrupt ? onInterrupt : null,
        ),
      ],
    );
  }
}

class _RoundCallButton extends StatelessWidget {
  const _RoundCallButton({
    required this.tooltip,
    required this.icon,
    required this.onPressed,
    this.onLongPress,
    this.backgroundColor,
    this.foregroundColor,
    this.size = 58,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;
  final VoidCallback? onLongPress;
  final Color? backgroundColor;
  final Color? foregroundColor;
  final double size;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Tooltip(
      message: tooltip,
      child: SizedBox.square(
        dimension: size,
        child: IconButton.filled(
          onPressed: onPressed,
          onLongPress: onLongPress,
          style: IconButton.styleFrom(
            backgroundColor: backgroundColor ?? scheme.surfaceContainerHighest,
            foregroundColor: foregroundColor ?? scheme.onSurface,
            disabledBackgroundColor: scheme.surfaceContainerHighest.withValues(
              alpha: 0.45,
            ),
            disabledForegroundColor: scheme.onSurfaceVariant.withValues(
              alpha: 0.45,
            ),
          ),
          icon: Icon(icon),
        ),
      ),
    );
  }
}
