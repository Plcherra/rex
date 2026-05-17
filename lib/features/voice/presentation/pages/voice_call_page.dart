import 'package:flutter/material.dart';
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
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final status = _statusFor(call);

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
                  controller.interrupt(reason: 'Rex was interrupted.');
                  controller.resumeListening();
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
      VoiceCallPhase.starting => _CallStatus(
        title: 'Starting',
        subtitle: 'Preparing microphone and audio session.',
        icon: Icons.more_horiz_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoiceCallPhase.listening => _CallStatus(
        title: 'Listening',
        subtitle: 'Speak naturally. Rex will answer after each turn.',
        icon: Icons.graphic_eq_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoiceCallPhase.capturingSpeech => _CallStatus(
        title: 'Hearing you',
        subtitle: 'Keep talking. Rex is capturing this turn.',
        icon: Icons.hearing_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoiceCallPhase.endpointing => _CallStatus(
        title: 'Got it',
        subtitle: 'Rex detected the end of your turn.',
        icon: Icons.check_rounded,
        color: (scheme) => scheme.tertiary,
      ),
      VoiceCallPhase.transcribing => _CallStatus(
        title: 'Transcribing',
        subtitle: 'Turning your voice into a message.',
        icon: Icons.short_text_rounded,
        color: (scheme) => scheme.tertiary,
      ),
      VoiceCallPhase.thinking => _CallStatus(
        title: 'Thinking',
        subtitle: 'Rex is using memory and context to answer.',
        icon: Icons.psychology_alt_rounded,
        color: (scheme) => scheme.secondary,
      ),
      VoiceCallPhase.speaking => _CallStatus(
        title: 'Speaking',
        subtitle: 'Rex is answering out loud.',
        icon: Icons.volume_up_rounded,
        color: (scheme) => scheme.primary,
      ),
      VoiceCallPhase.interrupted => _CallStatus(
        title: 'Interrupted',
        subtitle: 'Rex stopped speaking and is ready to listen.',
        icon: Icons.front_hand_rounded,
        color: (scheme) => scheme.tertiary,
      ),
      VoiceCallPhase.failed => _CallStatus(
        title: 'Call failed',
        subtitle: call.errorMessage ?? 'Something interrupted the voice call.',
        icon: Icons.error_outline_rounded,
        color: (scheme) => scheme.error,
      ),
      VoiceCallPhase.ended => _CallStatus(
        title: 'Call ended',
        subtitle: 'Your chat history stays in the conversation.',
        icon: Icons.call_end_rounded,
        color: (scheme) => scheme.onSurfaceVariant,
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
    final hasContent = transcript.isNotEmpty || response.isNotEmpty;

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
