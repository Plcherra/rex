import 'dart:async';

import 'package:audio_session/audio_session.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:permission_handler/permission_handler.dart';

import 'package:rex/core/config/app_config.dart';
import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/voice/data/audio_playback_service.dart';
import 'package:rex/features/voice/data/audio_recording_service.dart';
import 'package:rex/features/voice/data/audio_session_service.dart';
import 'package:rex/features/voice/data/background_voice_service.dart';
import 'package:rex/features/voice/data/cloud_voice_api.dart';
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

final audioRecordingServiceProvider = Provider<AudioRecordingService>(
  (ref) => PackageAudioRecordingService(),
);

final audioPlaybackServiceProvider = Provider<AudioPlaybackService>(
  (ref) => PackageAudioPlaybackService(),
);

final voiceAudioSessionServiceProvider = Provider<VoiceAudioSessionService>(
  (ref) => PackageVoiceAudioSessionService(),
);

final backgroundVoiceServiceProvider = Provider<BackgroundVoiceService>(
  (ref) => MethodChannelBackgroundVoiceService(),
);

final cloudVoiceApiProvider = Provider<CloudVoiceApi>((ref) => CloudVoiceApi());

final cloudVoiceEnabledProvider = Provider<bool>(
  (ref) => AppConfig.cloudVoiceEnabled,
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
  Future<MicrophonePermissionDecision> requestMicrophonePermission({
    bool includeSpeechRecognition = true,
  });

  Future<void> openSettings();
}

class PermissionHandlerMicrophonePermissionService
    implements MicrophonePermissionService {
  @override
  Future<MicrophonePermissionDecision> requestMicrophonePermission({
    bool includeSpeechRecognition = true,
  }) async {
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

    if (includeSpeechRecognition) {
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
    }

    return MicrophonePermissionDecision.granted;
  }

  @override
  Future<void> openSettings() async {
    try {
      await openAppSettings();
    } on MissingPluginException {
      // permission_handler does not provide a macOS implementation. The
      // recorder plugin and macOS app entitlements handle microphone access.
    }
  }

  Future<PermissionStatus> _requestPermission(Permission permission) async {
    try {
      final currentStatus = await permission.status;
      if (currentStatus.isGranted) {
        return currentStatus;
      }
      return permission.request();
    } on MissingPluginException {
      return PermissionStatus.granted;
    }
  }
}

class VoiceController extends Notifier<VoiceState> with WidgetsBindingObserver {
  int _voiceGeneration = 0;
  SpeechToTextService? _activeSpeechToTextService;
  TextToSpeechService? _activeTextToSpeechService;
  AudioRecordingService? _activeAudioRecordingService;
  AudioPlaybackService? _activeAudioPlaybackService;
  VoiceAudioSessionService? _activeAudioSessionService;
  BackgroundVoiceService? _activeBackgroundVoiceService;
  StreamSubscription<void>? _noisyAudioSubscription;
  StreamSubscription<AudioInterruptionEvent>? _audioInterruptionSubscription;

  @override
  VoiceState build() {
    WidgetsFlutterBinding.ensureInitialized();
    WidgetsBinding.instance.addObserver(this);
    ref.onDispose(() {
      WidgetsBinding.instance.removeObserver(this);
      _voiceGeneration++;
      unawaited(_noisyAudioSubscription?.cancel());
      unawaited(_audioInterruptionSubscription?.cancel());
      final speechToTextService = _activeSpeechToTextService;
      final textToSpeechService = _activeTextToSpeechService;
      final audioRecordingService = _activeAudioRecordingService;
      final audioPlaybackService = _activeAudioPlaybackService;
      final audioSessionService = _activeAudioSessionService;
      final backgroundVoiceService = _activeBackgroundVoiceService;
      if (speechToTextService != null) {
        unawaited(speechToTextService.cancel());
      }
      if (textToSpeechService != null) {
        unawaited(textToSpeechService.stop());
      }
      if (audioRecordingService != null) {
        unawaited(audioRecordingService.cancelRecording());
      }
      if (audioPlaybackService != null) {
        unawaited(audioPlaybackService.stop());
      }
      if (backgroundVoiceService != null) {
        unawaited(backgroundVoiceService.stop());
      }
      if (audioSessionService != null) {
        unawaited(audioSessionService.setActive(false));
      }
    });
    return const VoiceState();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.detached) {
      unawaited(cancelCurrentTurn());
    }
  }

  void reset() {
    _voiceGeneration++;
    state = const VoiceState();
  }

  Future<bool> startListening() async {
    if (!state.canStartListening) {
      return false;
    }

    if (ref.read(cloudVoiceEnabledProvider)) {
      return _startCloudRecording();
    }

    return _startLocalListening();
  }

  Future<bool> _startLocalListening() async {
    if (!state.canStartListening) {
      return false;
    }

    final generation = ++_voiceGeneration;
    final decision = await ref
        .read(microphonePermissionProvider)
        .requestMicrophonePermission(includeSpeechRecognition: true);
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

  Future<bool> _startCloudRecording() async {
    final generation = ++_voiceGeneration;
    final decision = await ref
        .read(microphonePermissionProvider)
        .requestMicrophonePermission(includeSpeechRecognition: false);
    if (!_isCurrentTurn(generation)) {
      return false;
    }
    if (decision != MicrophonePermissionDecision.granted) {
      denyPermission(
        _permissionMessage(decision, includeSpeechRecognition: false),
      );
      return false;
    }

    try {
      await _prepareAudioForVoiceTurn();
      await _backgroundVoiceService.start();
      await _audioRecordingService.startRecording();
    } catch (_) {
      unawaited(_activeBackgroundVoiceService?.stop());
      fail('Could not start voice recording.', generation: generation);
      return false;
    }
    if (!_isCurrentTurn(generation)) {
      return false;
    }

    state = const VoiceState(phase: VoicePhase.recording);
    return true;
  }

  Future<void> stopListening() async {
    if (ref.read(cloudVoiceEnabledProvider)) {
      await stopAndSubmitCurrentTranscript();
      return;
    }
    await _speechToTextService.stopListening();
  }

  Future<void> stopAndSubmitCurrentTranscript() async {
    if (ref.read(cloudVoiceEnabledProvider)) {
      await _stopCloudRecordingAndSubmit();
      return;
    }

    await stopListening();
    final generation = _voiceGeneration;
    final transcript = state.partialTranscript.trim();
    if (transcript.isEmpty) {
      fail(_noSpeechDetectedMessage(), generation: generation);
      return;
    }

    submitFinalTranscript(transcript, generation: generation);
  }

  Future<void> _stopCloudRecordingAndSubmit() async {
    final generation = _voiceGeneration;
    state = state.copyWith(phase: VoicePhase.uploading, clearError: true);

    final RecordedVoiceAudio? recording;
    try {
      recording = await _audioRecordingService.stopRecording();
    } catch (_) {
      fail('Could not finish voice recording.', generation: generation);
      return;
    }
    if (!_isCurrentTurn(generation)) {
      return;
    }
    if (recording == null) {
      fail(_noSpeechDetectedMessage(), generation: generation);
      return;
    }

    unawaited(_sendCloudRecording(recording, generation));
  }

  Future<void> _sendCloudRecording(
    RecordedVoiceAudio recording,
    int generation,
  ) async {
    try {
      state = state.copyWith(phase: VoicePhase.transcribing, clearError: true);
      final transcription = await ref
          .read(cloudVoiceApiProvider)
          .transcribe(
            audio: recording.file,
            inputMimeType: recording.inputMimeType,
          );
      if (!_isCurrentTurn(generation)) {
        return;
      }

      final transcript = transcription.transcript.trim();
      if (transcript.isEmpty) {
        fail(_noSpeechDetectedMessage(), generation: generation);
        return;
      }

      finishTranscription(transcript, generation: generation);
      startThinking(generation: generation);
      final responseText = await ref
          .read(chatProvider.notifier)
          .sendMessageForAssistantResponse(transcript, stream: true);
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

      state = state.copyWith(phase: VoicePhase.generatingSpeech);
      final synthesis = await ref
          .read(cloudVoiceApiProvider)
          .synthesize(responseText);
      if (!_isCurrentTurn(generation)) {
        return;
      }

      await startCloudSpeaking(
        responseText: responseText,
        audioBase64: synthesis.audioBase64,
        audioContentType: synthesis.audioContentType,
        generation: generation,
      );
    } on CloudVoiceApiException catch (error) {
      fail(error.message, generation: generation);
    } on Object catch (_) {
      fail('Cloud voice failed.', generation: generation);
    }
  }

  Future<void> cancelListening() async {
    _voiceGeneration++;
    if (ref.read(cloudVoiceEnabledProvider)) {
      await _audioRecordingService.cancelRecording();
      await _backgroundVoiceService.stop();
      await _audioSessionService.setActive(false);
    } else {
      await _speechToTextService.cancel();
    }
    state = const VoiceState();
  }

  Future<void> cancelCurrentTurn() async {
    _voiceGeneration++;
    ref.read(chatProvider.notifier).cancelStreaming();
    await _speechToTextService.cancel();
    await _textToSpeechService.stop();
    await _activeAudioRecordingService?.cancelRecording();
    await _activeAudioPlaybackService?.stop();
    await _backgroundVoiceService.stop();
    await _audioSessionService.setActive(false);
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
      await _prepareAudioForVoiceTurn();
      await _textToSpeechService.speak(
        responseText,
        onComplete: () => completeSpeaking(generation: activeGeneration),
        onError: (message) => fail(message, generation: activeGeneration),
      );
    } catch (_) {
      fail('Text-to-speech playback failed.', generation: activeGeneration);
    }
  }

  Future<void> startCloudSpeaking({
    required String responseText,
    required String audioBase64,
    required String audioContentType,
    int? generation,
  }) async {
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
      await _prepareAudioForVoiceTurn();
      await _audioPlaybackService.playBase64Audio(
        audioBase64,
        contentType: audioContentType,
        onComplete: () => completeSpeaking(generation: activeGeneration),
        onError: (message) => fail(message, generation: activeGeneration),
      );
    } catch (_) {
      fail('Voice playback failed.', generation: activeGeneration);
    }
  }

  void completeSpeaking({int? generation}) {
    if (!_isCurrentTurn(generation)) {
      return;
    }
    unawaited(_backgroundVoiceService.stop());
    unawaited(_audioSessionService.setActive(false));
    state = state.copyWith(phase: VoicePhase.idle, clearError: true);
  }

  Future<void> stopSpeaking() async {
    _voiceGeneration++;
    try {
      await _textToSpeechService.stop();
      await _activeAudioPlaybackService?.stop();
      completeSpeaking();
    } catch (_) {
      fail('Text-to-speech playback failed.');
    }
  }

  Future<void> pauseSpeaking() async {
    _voiceGeneration++;
    try {
      await _textToSpeechService.pause();
      await _activeAudioPlaybackService?.pause();
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

  Future<void> _prepareAudioForVoiceTurn() async {
    final audioSessionService = _audioSessionService;
    await audioSessionService.configureForVoiceTurn();
    _noisyAudioSubscription ??= audioSessionService.listenForNoisyAudio((
      message,
    ) {
      if (state.isBusy) {
        fail(message);
      }
    });
    _audioInterruptionSubscription ??= audioSessionService
        .listenForInterruptions((message) {
          if (state.isBusy) {
            fail(message);
          }
        });
  }

  String _permissionMessage(
    MicrophonePermissionDecision decision, {
    bool includeSpeechRecognition = true,
  }) {
    return switch (decision) {
      MicrophonePermissionDecision.permanentlyDenied =>
        includeSpeechRecognition
            ? 'Microphone or speech recognition permission is blocked. Enable it in Settings to talk to Rex.'
            : 'Microphone permission is blocked. Enable it in Settings to talk to Rex.',
      MicrophonePermissionDecision.restricted =>
        includeSpeechRecognition
            ? 'Microphone or speech recognition access is restricted on this device.'
            : 'Microphone access is restricted on this device.',
      MicrophonePermissionDecision.denied =>
        includeSpeechRecognition
            ? 'Microphone and speech recognition permission are required to talk to Rex.'
            : 'Microphone permission is required to talk to Rex.',
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

  AudioRecordingService get _audioRecordingService {
    final existingService = _activeAudioRecordingService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(audioRecordingServiceProvider);
    _activeAudioRecordingService = service;
    return service;
  }

  AudioPlaybackService get _audioPlaybackService {
    final existingService = _activeAudioPlaybackService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(audioPlaybackServiceProvider);
    _activeAudioPlaybackService = service;
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
