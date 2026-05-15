import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:permission_handler/permission_handler.dart';

import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/voice/data/speech_to_text_service.dart';
import 'package:rex/features/voice/data/text_to_speech_service.dart';
import 'package:rex/features/voice/domain/voice_state.dart';

final microphonePermissionProvider = Provider<MicrophonePermissionService>(
  (ref) => PermissionHandlerMicrophonePermissionService(),
);

final speechToTextServiceProvider = Provider<SpeechToTextService>(
  (ref) => PackageSpeechToTextService(),
);

final textToSpeechServiceProvider = Provider<TextToSpeechService>(
  (ref) => PackageTextToSpeechService(),
);

final voiceProvider = NotifierProvider<VoiceController, VoiceState>(
  VoiceController.new,
);

enum MicrophonePermissionDecision {
  granted,
  denied,
  permanentlyDenied,
  restricted,
}

abstract class MicrophonePermissionService {
  Future<MicrophonePermissionDecision> requestMicrophonePermission();

  Future<void> openSettings();
}

class PermissionHandlerMicrophonePermissionService
    implements MicrophonePermissionService {
  @override
  Future<MicrophonePermissionDecision> requestMicrophonePermission() async {
    final microphoneStatus = await _requestPermission(Permission.microphone);
    if (microphoneStatus.isPermanentlyDenied) {
      return MicrophonePermissionDecision.permanentlyDenied;
    }
    if (microphoneStatus.isRestricted) {
      return MicrophonePermissionDecision.restricted;
    }
    if (!microphoneStatus.isGranted) {
      return MicrophonePermissionDecision.denied;
    }

    final speechStatus = await _requestPermission(Permission.speech);
    if (speechStatus.isPermanentlyDenied) {
      return MicrophonePermissionDecision.permanentlyDenied;
    }
    if (speechStatus.isRestricted) {
      return MicrophonePermissionDecision.restricted;
    }
    if (!speechStatus.isGranted) {
      return MicrophonePermissionDecision.denied;
    }

    return MicrophonePermissionDecision.granted;
  }

  @override
  Future<void> openSettings() async {
    await openAppSettings();
  }

  Future<PermissionStatus> _requestPermission(Permission permission) async {
    final currentStatus = await permission.status;
    if (currentStatus.isGranted) {
      return currentStatus;
    }
    return permission.request();
  }
}

class VoiceController extends Notifier<VoiceState> {
  int _voiceGeneration = 0;
  SpeechToTextService? _activeSpeechToTextService;
  TextToSpeechService? _activeTextToSpeechService;

  @override
  VoiceState build() {
    ref.onDispose(() {
      _voiceGeneration++;
      final speechToTextService = _activeSpeechToTextService;
      final textToSpeechService = _activeTextToSpeechService;
      if (speechToTextService != null) {
        unawaited(speechToTextService.cancel());
      }
      if (textToSpeechService != null) {
        unawaited(textToSpeechService.stop());
      }
    });
    return const VoiceState();
  }

  void reset() {
    _voiceGeneration++;
    state = const VoiceState();
  }

  Future<bool> startListening() async {
    if (!state.canStartListening) {
      return false;
    }

    final generation = ++_voiceGeneration;
    final decision = await ref
        .read(microphonePermissionProvider)
        .requestMicrophonePermission();
    if (!_isCurrentTurn(generation)) {
      return false;
    }
    if (decision != MicrophonePermissionDecision.granted) {
      denyPermission(_permissionMessage(decision));
      return false;
    }

    final speechToTextService = _speechToTextService;
    final isAvailable = await speechToTextService.initialize(
      onError: (message) => fail(message, generation: generation),
    );
    if (!_isCurrentTurn(generation)) {
      return false;
    }
    if (!isAvailable) {
      return false;
    }

    state = const VoiceState(phase: VoicePhase.listening);
    await speechToTextService.startListening(
      onPartialTranscript: (transcript) =>
          updatePartialTranscript(transcript, generation: generation),
      onFinalTranscript: (transcript) =>
          submitFinalTranscript(transcript, generation: generation),
      onError: (message) => fail(message, generation: generation),
    );
    return true;
  }

  Future<void> stopListening() async {
    await _speechToTextService.stopListening();
  }

  Future<void> stopAndSubmitCurrentTranscript() async {
    await stopListening();
    final generation = _voiceGeneration;
    final transcript = state.partialTranscript.trim();
    if (transcript.isEmpty) {
      fail(_noSpeechDetectedMessage(), generation: generation);
      return;
    }

    submitFinalTranscript(transcript, generation: generation);
  }

  Future<void> cancelListening() async {
    _voiceGeneration++;
    await _speechToTextService.cancel();
    state = const VoiceState();
  }

  Future<void> cancelCurrentTurn() async {
    _voiceGeneration++;
    ref.read(chatProvider.notifier).cancelStreaming();
    await _speechToTextService.cancel();
    await _textToSpeechService.stop();
    state = const VoiceState();
  }

  void updatePartialTranscript(String transcript, {int? generation}) {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    state = state.copyWith(
      phase: VoicePhase.listening,
      partialTranscript: transcript,
      clearError: true,
    );
  }

  void finishTranscription(String transcript, {int? generation}) {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    state = state.copyWith(
      phase: VoicePhase.transcribing,
      finalTranscript: transcript,
      clearPartialTranscript: true,
      clearError: true,
    );
  }

  void submitFinalTranscript(String transcript, {int? generation}) {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    final activeGeneration = generation ?? _voiceGeneration;
    finishTranscription(transcript, generation: activeGeneration);
    unawaited(_sendTranscriptToChat(transcript, activeGeneration));
  }

  Future<void> _sendTranscriptToChat(String transcript, int generation) async {
    final message = transcript.trim();
    if (!_isCurrentTurn(generation)) {
      return;
    }
    if (message.isEmpty) {
      state = state.copyWith(phase: VoicePhase.idle);
      return;
    }

    startThinking(generation: generation);
    final responseText = await ref
        .read(chatProvider.notifier)
        .sendMessageForAssistantResponse(message, stream: true);
    if (!_isCurrentTurn(generation)) {
      return;
    }
    if (responseText == null) {
      final chatError = ref.read(chatProvider).errorMessage;
      fail(
        chatError ?? 'Rex could not answer that voice message.',
        generation: generation,
      );
      return;
    }

    await startSpeaking(responseText, generation: generation);
  }

  void startThinking({int? generation}) {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    state = state.copyWith(phase: VoicePhase.thinking, clearError: true);
  }

  Future<void> startSpeaking(String responseText, {int? generation}) async {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    final activeGeneration = generation ?? _voiceGeneration;
    state = state.copyWith(
      phase: VoicePhase.speaking,
      spokenResponseText: responseText,
      clearError: true,
    );

    try {
      await _textToSpeechService.speak(
        responseText,
        onComplete: () => completeSpeaking(generation: activeGeneration),
        onError: (message) => fail(message, generation: activeGeneration),
      );
    } catch (_) {
      fail('Text-to-speech playback failed.', generation: activeGeneration);
    }
  }

  void completeSpeaking({int? generation}) {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    state = state.copyWith(phase: VoicePhase.idle, clearError: true);
  }

  Future<void> stopSpeaking() async {
    _voiceGeneration++;
    try {
      await _textToSpeechService.stop();
      completeSpeaking();
    } catch (_) {
      fail('Text-to-speech playback failed.');
    }
  }

  Future<void> pauseSpeaking() async {
    _voiceGeneration++;
    try {
      await _textToSpeechService.pause();
      completeSpeaking();
    } catch (_) {
      fail('Text-to-speech playback failed.');
    }
  }

  void fail(String message, {int? generation}) {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    state = state.copyWith(phase: VoicePhase.failed, errorMessage: message);
  }

  void denyPermission(String message) {
    _voiceGeneration++;
    state = state.copyWith(
      phase: VoicePhase.permissionDenied,
      errorMessage: message,
      clearPartialTranscript: true,
    );
  }

  Future<void> openVoiceSettings() async {
    await ref.read(microphonePermissionProvider).openSettings();
  }

  String _permissionMessage(MicrophonePermissionDecision decision) {
    return switch (decision) {
      MicrophonePermissionDecision.permanentlyDenied =>
        'Microphone or speech recognition permission is blocked. Enable it in Settings to talk to Rex.',
      MicrophonePermissionDecision.restricted =>
        'Microphone or speech recognition access is restricted on this device.',
      MicrophonePermissionDecision.denied =>
        'Microphone and speech recognition permission are required to talk to Rex.',
      MicrophonePermissionDecision.granted => '',
    };
  }

  String _noSpeechDetectedMessage() {
    return 'I did not catch any audio. If you are using the iOS simulator, set Simulator > I/O > Audio Input to your Mac microphone and make sure macOS allows Simulator microphone access.';
  }

  bool _isCurrentTurn(int? generation) {
    return generation == null || generation == _voiceGeneration;
  }

  SpeechToTextService get _speechToTextService {
    final existingService = _activeSpeechToTextService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(speechToTextServiceProvider);
    _activeSpeechToTextService = service;
    return service;
  }

  TextToSpeechService get _textToSpeechService {
    final existingService = _activeTextToSpeechService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(textToSpeechServiceProvider);
    _activeTextToSpeechService = service;
    return service;
  }
}
