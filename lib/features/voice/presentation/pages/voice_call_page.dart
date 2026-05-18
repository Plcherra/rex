import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';

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
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final status = _statusFor(call);
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
            onPressed: () {
              controller.reset();
            },
            icon: const Icon(Icons.restart_alt_rounded),
            tooltip: 'Reset call',
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            children: [
              const Spacer(),
              AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                width: 136,
                height: 136,
                decoration: BoxDecoration(
                  color: status.color(scheme).withValues(alpha: 0.14),
                  shape: BoxShape.circle,
                ),
                child: Icon(status.icon, size: 58, color: status.color(scheme)),
              ),
              const SizedBox(height: 24),
              Text(
                status.title,
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                status.subtitle,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: scheme.onSurfaceVariant,
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 28),
              _CallTranscriptPanel(call: call),
              const Spacer(),
              VoiceCallControls(
                state: call,
                onStart: () {
                  controller.startCall();
                },
                onEnd: () {
                  controller.endCall();
                  Navigator.of(context).maybePop();
                },
                onToggleMute: controller.toggleMuted,
                onInterrupt: () {
                  controller.interruptAndListen(reason: 'Rex was interrupted.');
                },
                onRetry: () {
                  controller.startCall();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  _CallStatus _statusFor(VoiceCallState call) {
    if (call.isMuted && call.phase == VoiceCallPhase.listening) {
      return _CallStatus(
        title: 'Mic muted',
        subtitle: 'Unmute when you want Rex to listen again.',
        icon: Icons.mic_off_rounded,
        color: (scheme) => scheme.tertiary,
      );
    }

    return switch (call.phase) {
      VoiceCallPhase.idle => _CallStatus(
        title: 'Ready to call',
        subtitle: 'Start a voice call when you want to talk hands-free.',
        icon: Icons.call_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoiceCallPhase.listening => _CallStatus(
        title: 'Listening',
        subtitle: 'Speak naturally. Your words appear here live.',
        icon: Icons.graphic_eq_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoiceCallPhase.thinking => _CallStatus(
        title: 'Thinking',
        subtitle: 'Rex is answering.',
        icon: Icons.psychology_alt_rounded,
        color: (scheme) => scheme.secondary,
      ),
      VoiceCallPhase.speaking => _CallStatus(
        title: 'Speaking',
        subtitle: 'Rex is answering out loud.',
        icon: Icons.volume_up_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoiceCallPhase.failed => _CallStatus(
        title: 'Call failed',
        subtitle: call.errorMessage ?? 'Something interrupted the voice call.',
        icon: Icons.error_outline_rounded,
        color: (scheme) => scheme.error,
      ),
    };
  }
}

class _CallTranscriptPanel extends StatelessWidget {
  const _CallTranscriptPanel({required this.call});

  final VoiceCallState call;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final transcript = call.currentTranscript.trim();
    final response = call.lastAssistantResponse.trim();
    final isThinking = call.phase == VoiceCallPhase.thinking;
    final hasContent =
        transcript.isNotEmpty || response.isNotEmpty || isThinking;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.5)),
      ),
      child: SizedBox(
        width: double.infinity,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: hasContent
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (transcript.isNotEmpty) ...[
                      _PanelLabel(label: 'You', color: scheme.primary),
                      const SizedBox(height: 6),
                      Text(transcript, style: theme.textTheme.bodyLarge),
                    ],
                    if (transcript.isNotEmpty && response.isNotEmpty)
                      const SizedBox(height: 16),
                    if (response.isNotEmpty) ...[
                      _PanelLabel(label: 'Rex', color: scheme.secondary),
                      const SizedBox(height: 6),
                      Text(response, style: theme.textTheme.bodyLarge),
                    ] else if (isThinking) ...[
                      _ThinkingLabel(color: scheme.secondary),
                    ],
                  ],
                )
              : Text(
                  'Your words and Rex response will appear here during the call.',
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: scheme.onSurfaceVariant,
                    fontStyle: FontStyle.italic,
                    height: 1.35,
                  ),
                ),
        ),
      ),
    );
  }
}

class _PanelLabel extends StatelessWidget {
  const _PanelLabel({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      style: Theme.of(context).textTheme.labelMedium?.copyWith(
        color: color,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

class _ThinkingLabel extends StatelessWidget {
  const _ThinkingLabel({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _PanelLabel(label: 'Rex', color: color),
        const SizedBox(width: 10),
        SizedBox.square(
          dimension: 14,
          child: CircularProgressIndicator(strokeWidth: 2, color: color),
        ),
        const SizedBox(width: 8),
        Text(
          'thinking',
          style: theme.textTheme.bodyMedium?.copyWith(color: color),
        ),
      ],
    );
  }
}

class _CallStatus {
  const _CallStatus({
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
