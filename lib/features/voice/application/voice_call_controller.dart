import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/voice/application/voice_controller.dart';
import 'package:rex/features/voice/data/audio_capture_service.dart';
import 'package:rex/features/voice/data/audio_playback_service.dart';
import 'package:rex/features/voice/data/audio_recording_service.dart';
import 'package:rex/features/voice/data/audio_session_service.dart';
import 'package:rex/features/voice/data/background_voice_service.dart';
import 'package:rex/features/voice/data/cloud_voice_api.dart';
import 'package:rex/features/voice/domain/voice_call_state.dart';

final audioCaptureServiceProvider = Provider<AudioCaptureService>(
  (ref) => PackageAudioCaptureService(),
);

final voiceCaptureConfigProvider = Provider<VoiceCaptureConfig>(
  (ref) => const VoiceCaptureConfig(),
);

final voiceCallProvider = NotifierProvider<VoiceCallController, VoiceCallState>(
  VoiceCallController.new,
);

typedef VoiceCallNow = DateTime Function();

final voiceCallNowProvider = Provider<VoiceCallNow>((ref) => DateTime.now);

class VoiceCallController extends Notifier<VoiceCallState> {
  int _callGeneration = 0;
  AudioCaptureService? _activeCaptureService;
  AudioPlaybackService? _activePlaybackService;
  VoiceAudioSessionService? _activeAudioSessionService;
  BackgroundVoiceService? _activeBackgroundVoiceService;
  var _isStartingCall = false;

  @override
  VoiceCallState build() {
    ref.onDispose(() {
      _callGeneration++;
      final captureService = _activeCaptureService;
      final playbackService = _activePlaybackService;
      final audioSessionService = _activeAudioSessionService;
      final backgroundVoiceService = _activeBackgroundVoiceService;
      if (captureService != null) {
        unawaited(captureService.cancel());
      }
      if (playbackService != null) {
        unawaited(playbackService.stop());
      }
      if (backgroundVoiceService != null) {
        unawaited(backgroundVoiceService.stop());
      }
      if (audioSessionService != null) {
        unawaited(audioSessionService.setActive(false));
      }
    });
    return const VoiceCallState();
  }

  Future<bool> startCall({String? conversationId}) async {
    if (_isStartingCall || !state.canStartCall) {
      return false;
    }

    _isStartingCall = true;
    final generation = ++_callGeneration;
    final startedAt = ref.read(voiceCallNowProvider)();
    final activeConversationId =
        conversationId ?? ref.read(chatProvider).conversationId;

    state = VoiceCallState(
      phase: VoiceCallPhase.starting,
      conversationId: activeConversationId,
      callStartedAt: startedAt,
    );
    final permissionDecision = await ref
        .read(microphonePermissionProvider)
        .requestMicrophonePermission(includeSpeechRecognition: false);
    if (!_isCurrentCall(generation)) {
      _isStartingCall = false;
      return false;
    }
    if (permissionDecision != MicrophonePermissionDecision.granted) {
      fail(_permissionMessage(permissionDecision));
      _isStartingCall = false;
      return false;
    }

    try {
      await _audioSessionService.configureForVoiceTurn();
      await _backgroundVoiceService.start();
    } on Object {
      fail('Could not start the voice call audio session.');
      _isStartingCall = false;
      return false;
    }
    if (!_isCurrentCall(generation)) {
      _isStartingCall = false;
      return false;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.listening,
      clearError: true,
      clearCallEndedAt: true,
    );
    _isStartingCall = false;
    _startListeningCycle(generation);
    return true;
  }

  void startCapturingSpeech({String transcript = ''}) {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.capturingSpeech,
      currentTranscript: transcript,
      clearError: true,
    );
  }

  void updateTranscript(String transcript) {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.capturingSpeech,
      currentTranscript: transcript,
      clearError: true,
    );
  }

  void endpointUtterance() {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(phase: VoiceCallPhase.endpointing, clearError: true);
  }

  void startTranscribing() {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.transcribing,
      clearError: true,
    );
  }

  void startThinking({String? finalTranscript}) {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.thinking,
      currentTranscript: finalTranscript,
      clearError: true,
    );
  }

  void startSpeaking(String responseText) {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.speaking,
      lastAssistantResponse: responseText,
      clearError: true,
    );
  }

  void completeSpeaking() {
    if (state.phase != VoiceCallPhase.speaking) {
      return;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.listening,
      clearCurrentTranscript: true,
      clearError: true,
    );
    _startListeningCycle(_callGeneration);
  }

  void interrupt({String? reason}) {
    if (!state.isCallActive) {
      return;
    }
    _callGeneration++;
    unawaited(_playbackService.stop());

    state = state.copyWith(
      phase: VoiceCallPhase.interrupted,
      errorMessage: reason,
    );
  }

  void setMuted(bool isMuted) {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(isMuted: isMuted);
    if (isMuted) {
      _callGeneration++;
      unawaited(_captureService.cancel());
    } else if (state.phase == VoiceCallPhase.listening) {
      _startListeningCycle(++_callGeneration);
    }
  }

  void toggleMuted() {
    setMuted(!state.isMuted);
  }

  void resumeListening() {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(
      phase: VoiceCallPhase.listening,
      clearCurrentTranscript: true,
      clearError: true,
    );
    _startListeningCycle(_callGeneration);
  }

  void fail(String message) {
    _callGeneration++;
    unawaited(_captureService.cancel());
    unawaited(_playbackService.stop());
    unawaited(_backgroundVoiceService.stop());
    unawaited(_audioSessionService.setActive(false));
    state = state.copyWith(
      phase: VoiceCallPhase.failed,
      errorMessage: message,
      callEndedAt: ref.read(voiceCallNowProvider)(),
    );
  }

  void endCall() {
    if (!state.canEndCall) {
      return;
    }

    _callGeneration++;
    unawaited(_captureService.cancel());
    unawaited(_playbackService.stop());
    unawaited(_backgroundVoiceService.stop());
    unawaited(_audioSessionService.setActive(false));
    state = state.copyWith(
      phase: VoiceCallPhase.ended,
      callEndedAt: ref.read(voiceCallNowProvider)(),
      clearError: true,
    );
  }

  void reset() {
    _callGeneration++;
    unawaited(_captureService.cancel());
    unawaited(_playbackService.stop());
    unawaited(_backgroundVoiceService.stop());
    unawaited(_audioSessionService.setActive(false));
    state = const VoiceCallState();
  }

  void _startListeningCycle(int generation) {
    if (!_isCurrentCall(generation) ||
        state.phase != VoiceCallPhase.listening ||
        state.isMuted) {
      return;
    }

    unawaited(_captureNextUtterance(generation));
  }

  Future<void> _captureNextUtterance(int generation) async {
    if (!_isCurrentCall(generation) ||
        state.phase != VoiceCallPhase.listening ||
        state.isMuted) {
      return;
    }

    final RecordedVoiceAudio? recording;
    try {
      recording = await _captureService.captureUtterance(
        config: ref.read(voiceCaptureConfigProvider),
        onSpeechStart: () {
          if (_isCurrentCall(generation) &&
              state.phase == VoiceCallPhase.listening) {
            startCapturingSpeech();
          }
        },
      );
    } on Object {
      if (_isCurrentCall(generation)) {
        fail('Could not capture voice audio.');
      }
      return;
    }
    if (!_isCurrentCall(generation) || !state.isCallActive) {
      return;
    }
    if (recording == null) {
      if (state.phase == VoiceCallPhase.listening ||
          state.phase == VoiceCallPhase.capturingSpeech) {
        resumeListening();
      }
      return;
    }

    endpointUtterance();
    await _sendCapturedUtterance(recording, generation);
  }

  Future<void> _sendCapturedUtterance(
    RecordedVoiceAudio recording,
    int generation,
  ) async {
    if (!_isCurrentCall(generation)) {
      return;
    }

    try {
      startTranscribing();
      final response = await ref
          .read(cloudVoiceApiProvider)
          .sendVoiceTurn(
            audio: recording.file,
            inputMimeType: recording.inputMimeType,
            conversationId: state.conversationId,
          );
      if (!_isCurrentCall(generation)) {
        return;
      }

      ref
          .read(chatProvider.notifier)
          .applyBackendMessages(
            conversationId: response.conversationId,
            messages: response.messages,
            fallbackAssistantResponse: response.responseText,
          );

      startThinking(finalTranscript: response.transcript);
      startSpeaking(response.responseText);
      await _playbackService.playBase64Audio(
        response.audioBase64,
        contentType: response.audioContentType,
        onComplete: () {
          if (_isCurrentCall(generation)) {
            completeSpeaking();
          }
        },
        onError: (message) {
          if (_isCurrentCall(generation)) {
            fail(message);
          }
        },
      );
    } on CloudVoiceApiException catch (error) {
      if (_isCurrentCall(generation)) {
        fail(error.message);
      }
    } on Object {
      if (_isCurrentCall(generation)) {
        fail('Active voice call failed.');
      }
    }
  }

  bool _isCurrentCall(int generation) => generation == _callGeneration;

  String _permissionMessage(MicrophonePermissionDecision decision) {
    return switch (decision) {
      MicrophonePermissionDecision.permanentlyDenied =>
        'Microphone permission is blocked. Enable it in Settings to call Rex.',
      MicrophonePermissionDecision.restricted =>
        'Microphone access is restricted on this device.',
      MicrophonePermissionDecision.denied =>
        'Microphone permission is required to call Rex.',
      MicrophonePermissionDecision.granted => '',
    };
  }

  AudioCaptureService get _captureService {
    final existingService = _activeCaptureService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(audioCaptureServiceProvider);
    _activeCaptureService = service;
    return service;
  }

  AudioPlaybackService get _playbackService {
    final existingService = _activePlaybackService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(audioPlaybackServiceProvider);
    _activePlaybackService = service;
    return service;
  }

  VoiceAudioSessionService get _audioSessionService {
    final existingService = _activeAudioSessionService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(voiceAudioSessionServiceProvider);
    _activeAudioSessionService = service;
    return service;
  }

  BackgroundVoiceService get _backgroundVoiceService {
    final existingService = _activeBackgroundVoiceService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(backgroundVoiceServiceProvider);
    _activeBackgroundVoiceService = service;
    return service;
  }
}
