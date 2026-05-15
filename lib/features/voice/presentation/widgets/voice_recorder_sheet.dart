import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/core/providers.dart';
import 'package:rex/features/voice/domain/voice_state.dart';

class VoiceRecorderSheet extends ConsumerStatefulWidget {
  const VoiceRecorderSheet({super.key, this.autoStart = true});

  final bool autoStart;

  @override
  ConsumerState<VoiceRecorderSheet> createState() => _VoiceRecorderSheetState();
}

class _VoiceRecorderSheetState extends ConsumerState<VoiceRecorderSheet> {
  var _didAutoStart = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !widget.autoStart || _didAutoStart) {
        return;
      }
      _didAutoStart = true;
      final voice = ref.read(voiceProvider);
      if (voice.canStartListening) {
        ref.read(voiceProvider.notifier).startListening();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final voice = ref.watch(voiceProvider);
    final controller = ref.read(voiceProvider.notifier);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return SafeArea(
      top: false,
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          12,
          20,
          MediaQuery.viewInsetsOf(context).bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 42,
              height: 4,
              decoration: BoxDecoration(
                color: scheme.outlineVariant,
                borderRadius: BorderRadius.circular(999),
              ),
            ),
            const SizedBox(height: 18),
            _VoiceStatusHeader(voice: voice),
            const SizedBox(height: 18),
            _TranscriptPanel(voice: voice),
            const SizedBox(height: 18),
            _VoiceActions(
              voice: voice,
              onStart: controller.startListening,
              onStopListening: controller.stopAndSubmitCurrentTranscript,
              onCancelListening: controller.cancelListening,
              onCancelTurn: controller.cancelCurrentTurn,
              onStopSpeaking: controller.stopSpeaking,
              onRetry: controller.startListening,
              onOpenSettings: controller.openVoiceSettings,
              onClose: () => Navigator.of(context).maybePop(),
            ),
          ],
        ),
      ),
    );
  }
}

class _VoiceStatusHeader extends StatelessWidget {
  const _VoiceStatusHeader({required this.voice});

  final VoiceState voice;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final status = _statusFor(voice.phase);

    return Column(
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: 74,
          height: 74,
          decoration: BoxDecoration(
            color: status.color(scheme).withValues(alpha: 0.14),
            shape: BoxShape.circle,
          ),
          child: Icon(status.icon, size: 34, color: status.color(scheme)),
        ),
        const SizedBox(height: 14),
        Text(
          status.title,
          textAlign: TextAlign.center,
          style: theme.textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          status.subtitle,
          textAlign: TextAlign.center,
          style: theme.textTheme.bodyMedium?.copyWith(
            color: scheme.onSurfaceVariant,
            height: 1.35,
          ),
        ),
      ],
    );
  }

  _VoiceStatus _statusFor(VoicePhase phase) {
    return switch (phase) {
      VoicePhase.idle => _VoiceStatus(
        title: 'Ready when you are',
        subtitle: 'Tap the mic and talk to Rex naturally.',
        icon: Icons.mic_none_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoicePhase.listening => _VoiceStatus(
        title: 'Listening',
        subtitle: 'Say what you need. Stop when you are done.',
        icon: Icons.graphic_eq_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoicePhase.transcribing => _VoiceStatus(
        title: 'Transcribing',
        subtitle: 'Rex is turning your voice into a message.',
        icon: Icons.short_text_rounded,
        color: (scheme) => scheme.tertiary,
      ),
      VoicePhase.thinking => _VoiceStatus(
        title: 'Thinking',
        subtitle: 'Rex is answering through the normal chat pipeline.',
        icon: Icons.psychology_alt_rounded,
        color: (scheme) => scheme.secondary,
      ),
      VoicePhase.speaking => _VoiceStatus(
        title: 'Speaking',
        subtitle: 'Rex is reading the response out loud.',
        icon: Icons.volume_up_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoicePhase.failed => _VoiceStatus(
        title: 'Voice failed',
        subtitle: voice.errorMessage ?? 'Something interrupted voice mode.',
        icon: Icons.error_outline_rounded,
        color: (scheme) => scheme.error,
      ),
      VoicePhase.permissionDenied => _VoiceStatus(
        title: 'Microphone blocked',
        subtitle: voice.errorMessage ?? 'Rex needs microphone access first.',
        icon: Icons.mic_off_rounded,
        color: (scheme) => scheme.error,
      ),
    };
  }
}

class _TranscriptPanel extends StatelessWidget {
  const _TranscriptPanel({required this.voice});

  final VoiceState voice;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final text = _displayText();
    final isPlaceholder = text == null;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 92),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.5)),
      ),
      padding: const EdgeInsets.all(16),
      child: Text(
        text ?? 'Your words and Rex’s spoken response will appear here.',
        style: theme.textTheme.bodyLarge?.copyWith(
          color: isPlaceholder ? scheme.onSurfaceVariant : scheme.onSurface,
          height: 1.4,
          fontStyle: isPlaceholder ? FontStyle.italic : FontStyle.normal,
        ),
      ),
    );
  }

  String? _displayText() {
    if (voice.phase == VoicePhase.speaking &&
        voice.spokenResponseText.trim().isNotEmpty) {
      return voice.spokenResponseText.trim();
    }
    if (voice.partialTranscript.trim().isNotEmpty) {
      return voice.partialTranscript.trim();
    }
    if (voice.finalTranscript.trim().isNotEmpty) {
      return voice.finalTranscript.trim();
    }
    if (voice.errorMessage?.trim().isNotEmpty ?? false) {
      return voice.errorMessage!.trim();
    }
    return null;
  }
}

class _VoiceActions extends StatelessWidget {
  const _VoiceActions({
    required this.voice,
    required this.onStart,
    required this.onStopListening,
    required this.onCancelListening,
    required this.onCancelTurn,
    required this.onStopSpeaking,
    required this.onRetry,
    required this.onOpenSettings,
    required this.onClose,
  });

  final VoiceState voice;
  final Future<bool> Function() onStart;
  final Future<void> Function() onStopListening;
  final Future<void> Function() onCancelListening;
  final Future<void> Function() onCancelTurn;
  final Future<void> Function() onStopSpeaking;
  final Future<bool> Function() onRetry;
  final Future<void> Function() onOpenSettings;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return switch (voice.phase) {
      VoicePhase.idle => _ActionRow(
        primaryLabel: 'Start talking',
        primaryIcon: Icons.mic_rounded,
        onPrimary: () async {
          await onStart();
        },
        secondaryLabel: 'Close',
        onSecondary: onClose,
      ),
      VoicePhase.listening => _ActionRow(
        primaryLabel: 'Stop',
        primaryIcon: Icons.stop_rounded,
        onPrimary: onStopListening,
        secondaryLabel: 'Cancel',
        onSecondary: () {
          onCancelListening();
        },
      ),
      VoicePhase.transcribing ||
      VoicePhase.thinking => _BusyActions(onCancel: onCancelTurn),
      VoicePhase.speaking => _ActionRow(
        primaryLabel: 'Stop playback',
        primaryIcon: Icons.stop_rounded,
        onPrimary: onStopSpeaking,
        secondaryLabel: 'Close',
        onSecondary: onClose,
      ),
      VoicePhase.failed => _ActionRow(
        primaryLabel: 'Try again',
        primaryIcon: Icons.refresh_rounded,
        onPrimary: () async {
          await onRetry();
        },
        secondaryLabel: 'Close',
        onSecondary: onClose,
      ),
      VoicePhase.permissionDenied => _PermissionDeniedActions(
        onOpenSettings: onOpenSettings,
        onRetry: onRetry,
        onClose: onClose,
      ),
    };
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.primaryLabel,
    required this.primaryIcon,
    required this.onPrimary,
    required this.secondaryLabel,
    required this.onSecondary,
  });

  final String primaryLabel;
  final IconData primaryIcon;
  final Future<void> Function() onPrimary;
  final String secondaryLabel;
  final VoidCallback onSecondary;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: FilledButton.icon(
            onPressed: onPrimary,
            icon: Icon(primaryIcon),
            label: Text(primaryLabel),
          ),
        ),
        const SizedBox(width: 10),
        TextButton(onPressed: onSecondary, child: Text(secondaryLabel)),
      ],
    );
  }
}

class _BusyActions extends StatelessWidget {
  const _BusyActions({required this.onCancel});

  final Future<void> Function() onCancel;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 10),
          child: LinearProgressIndicator(),
        ),
        const SizedBox(height: 8),
        TextButton.icon(
          onPressed: onCancel,
          icon: const Icon(Icons.close_rounded),
          label: const Text('Cancel'),
        ),
      ],
    );
  }
}

class _PermissionDeniedActions extends StatelessWidget {
  const _PermissionDeniedActions({
    required this.onOpenSettings,
    required this.onRetry,
    required this.onClose,
  });

  final Future<void> Function() onOpenSettings;
  final Future<bool> Function() onRetry;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: onOpenSettings,
            icon: const Icon(Icons.settings_rounded),
            label: const Text('Open Settings'),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextButton(
              onPressed: () {
                onRetry();
              },
              child: const Text('Try again'),
            ),
            const SizedBox(width: 8),
            TextButton(onPressed: onClose, child: const Text('Close')),
          ],
        ),
      ],
    );
  }
}

class _VoiceStatus {
  const _VoiceStatus({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final Color Function(ColorScheme scheme) color;
}
