import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rex/core/config/app_config.dart';
import 'package:rex/features/chat/application/chat_controller.dart';
import 'package:rex/features/chat/data/chat_models.dart';
import 'package:rex/features/voice/application/voice_controller.dart';
import 'package:rex/features/voice/data/audio_capture_service.dart';
import 'package:rex/features/voice/data/audio_playback_service.dart';
import 'package:rex/features/voice/data/audio_recording_service.dart';
import 'package:rex/features/voice/data/audio_session_service.dart';
import 'package:rex/features/voice/data/background_voice_service.dart';
import 'package:rex/features/voice/data/cloud_voice_api.dart';
import 'package:rex/features/voice/data/streaming_audio_capture_service.dart';
import 'package:rex/features/voice/data/streaming_audio_playback_queue.dart';
import 'package:rex/features/voice/data/streaming_voice_api.dart';
import 'package:rex/features/voice/domain/voice_call_state.dart';

final audioCaptureServiceProvider = Provider<AudioCaptureService>(
  (ref) => PackageAudioCaptureService(),
);

final streamingAudioCaptureServiceProvider =
    Provider<StreamingAudioCaptureService>(
      (ref) => PackageStreamingAudioCaptureService(),
    );

final bargeInDetectionServiceProvider = Provider<BargeInDetectionService>(
  (ref) => PackageBargeInDetectionService(),
);

final streamingVoiceApiProvider = Provider<StreamingVoiceApi>(
  (ref) => StreamingVoiceApi(),
);

final streamingAudioPlaybackQueueProvider =
    Provider<StreamingAudioPlaybackQueue>(
      (ref) =>
          StreamingAudioPlaybackQueue(ref.read(audioPlaybackServiceProvider)),
    );

final streamingVoiceEnabledProvider = Provider<bool>(
  (ref) => AppConfig.streamingVoiceEnabled,
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
  StreamingAudioCaptureService? _activeStreamingCaptureService;
  StreamingVoiceSession? _activeStreamingSession;
  AudioPlaybackService? _activePlaybackService;
  StreamingAudioPlaybackQueue? _activeStreamingPlaybackQueue;
  BargeInDetectionService? _activeBargeInDetectionService;
  VoiceAudioSessionService? _activeAudioSessionService;
  BackgroundVoiceService? _activeBackgroundVoiceService;
  var _finalTranscriptBuffer = '';
  var _partialTranscriptBuffer = '';
  var _isStartingCall = false;
  var _isBargeInMonitoring = false;

  @override
  VoiceCallState build() {
    ref.onDispose(() {
      _callGeneration++;
      final captureService = _activeCaptureService;
      final playbackService = _activePlaybackService;
      final streamingPlaybackQueue = _activeStreamingPlaybackQueue;
      final bargeInDetectionService = _activeBargeInDetectionService;
      final streamingCaptureService = _activeStreamingCaptureService;
      final streamingSession = _activeStreamingSession;
      final audioSessionService = _activeAudioSessionService;
      final backgroundVoiceService = _activeBackgroundVoiceService;
      if (captureService != null) {
        unawaited(captureService.cancel());
      }
      if (streamingCaptureService != null) {
        unawaited(streamingCaptureService.cancel());
      }
      if (streamingSession != null) {
        unawaited(streamingSession.endSession());
      }
      if (streamingPlaybackQueue != null) {
        unawaited(streamingPlaybackQueue.cancel());
      }
      if (bargeInDetectionService != null) {
        unawaited(bargeInDetectionService.stop());
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
    _clearVisibleTranscript();
    final startedAt = ref.read(voiceCallNowProvider)();
    final activeConversationId =
        conversationId ?? ref.read(chatProvider).conversationId;

    state = VoiceCallState(
      phase: VoiceCallPhase.listening,
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
      phase: VoiceCallPhase.listening,
      currentTranscript: transcript,
      clearError: true,
    );
  }

  void updateTranscript(String transcript, {bool isFinal = false}) {
    if (!state.isCallActive) {
      return;
    }

    if (isFinal) {
      _appendFinalTranscript(transcript);
    } else {
      _partialTranscriptBuffer = transcript.trim();
    }

    state = state.copyWith(
      phase: VoiceCallPhase.listening,
      currentTranscript: _visibleTranscript(),
      clearError: true,
    );
  }

  void endpointUtterance() {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(phase: VoiceCallPhase.thinking, clearError: true);
  }

  void startTranscribing() {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(phase: VoiceCallPhase.thinking, clearError: true);
  }

  void startThinking({String? finalTranscript}) {
    if (!state.isCallActive) {
      return;
    }

    if (finalTranscript != null) {
      _appendFinalTranscript(finalTranscript);
    }

    state = state.copyWith(
      phase: VoiceCallPhase.thinking,
      currentTranscript: _visibleTranscript(),
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
    _clearVisibleTranscript();
    _startListeningCycle(_callGeneration);
  }

  void interrupt({String? reason}) {
    if (!state.isCallActive) {
      return;
    }
    _callGeneration++;
    unawaited(_captureService.cancel());
    unawaited(_streamingCaptureService.cancel());
    _stopBargeInMonitoring();
    final streamingSession = _activeStreamingSession;
    _activeStreamingSession = null;
    streamingSession?.interrupt();
    unawaited(_streamingPlaybackQueue.cancel());
    unawaited(streamingSession?.endSession());
    unawaited(_playbackService.stop());

    state = state.copyWith(
      phase: VoiceCallPhase.listening,
      errorMessage: reason,
    );
  }

  void interruptAndListen({String? reason}) {
    if (!state.isCallActive) {
      return;
    }

    final generation = ++_callGeneration;
    unawaited(_captureService.cancel());
    unawaited(_streamingCaptureService.cancel());
    _stopBargeInMonitoring();
    final streamingSession = _activeStreamingSession;
    _activeStreamingSession = null;
    streamingSession?.interrupt();
    unawaited(_streamingPlaybackQueue.cancel());
    unawaited(streamingSession?.endSession());
    unawaited(_playbackService.stop());

    state = state.copyWith(
      phase: VoiceCallPhase.listening,
      clearCurrentTranscript: true,
      clearError: true,
    );
    _clearVisibleTranscript();
    _startListeningCycle(generation);
  }

  void setMuted(bool isMuted) {
    if (!state.isCallActive) {
      return;
    }

    state = state.copyWith(isMuted: isMuted);
    if (isMuted) {
      _callGeneration++;
      unawaited(_captureService.cancel());
      unawaited(_streamingCaptureService.cancel());
      _stopBargeInMonitoring();
      final streamingSession = _activeStreamingSession;
      _activeStreamingSession = null;
      streamingSession?.interrupt();
      unawaited(_streamingPlaybackQueue.cancel());
      unawaited(streamingSession?.endSession());
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
    _clearVisibleTranscript();
    _startListeningCycle(_callGeneration);
  }

  void fail(String message) {
    _callGeneration++;
    unawaited(_captureService.cancel());
    unawaited(_streamingCaptureService.cancel());
    _stopBargeInMonitoring();
    final streamingSession = _activeStreamingSession;
    _activeStreamingSession = null;
    streamingSession?.interrupt();
    unawaited(_streamingPlaybackQueue.cancel());
    unawaited(streamingSession?.endSession());
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
    unawaited(_streamingCaptureService.cancel());
    _stopBargeInMonitoring();
    final streamingSession = _activeStreamingSession;
    _activeStreamingSession = null;
    streamingSession?.interrupt();
    unawaited(_streamingPlaybackQueue.cancel());
    unawaited(streamingSession?.endSession());
    unawaited(_playbackService.stop());
    unawaited(_backgroundVoiceService.stop());
    unawaited(_audioSessionService.setActive(false));
    state = state.copyWith(
      phase: VoiceCallPhase.idle,
      callEndedAt: ref.read(voiceCallNowProvider)(),
      clearError: true,
    );
    _clearVisibleTranscript();
  }

  void reset() {
    _callGeneration++;
    unawaited(_captureService.cancel());
    unawaited(_streamingCaptureService.cancel());
    _stopBargeInMonitoring();
    final streamingSession = _activeStreamingSession;
    _activeStreamingSession = null;
    streamingSession?.interrupt();
    unawaited(_streamingPlaybackQueue.cancel());
    unawaited(streamingSession?.endSession());
    unawaited(_playbackService.stop());
    unawaited(_backgroundVoiceService.stop());
    unawaited(_audioSessionService.setActive(false));
    _clearVisibleTranscript();
    state = const VoiceCallState();
  }

  void _startListeningCycle(int generation) {
    if (!_isCurrentCall(generation) ||
        state.phase != VoiceCallPhase.listening ||
        state.isMuted) {
      return;
    }

    if (ref.read(streamingVoiceEnabledProvider)) {
      unawaited(_streamNextUtterance(generation));
    } else {
      unawaited(_captureNextUtterance(generation));
    }
  }

  Future<void> _streamNextUtterance(int generation) async {
    if (!_isCurrentCall(generation) ||
        state.phase != VoiceCallPhase.listening ||
        state.isMuted) {
      return;
    }

    final StreamingVoiceSession session;
    try {
      session = await ref
          .read(streamingVoiceApiProvider)
          .connect(conversationId: state.conversationId);
      _activeStreamingSession = session;
      unawaited(_handleStreamingEvents(session, generation));
    } on StreamingVoiceApiException catch (error) {
      if (_isCurrentCall(generation)) {
        fail(error.message);
      }
      return;
    } on Object {
      if (_isCurrentCall(generation)) {
        fail('Could not open Rex voice stream.');
      }
      return;
    }

    final bool capturedAudio;
    try {
      capturedAudio = await _streamingCaptureService.streamUtterance(
        config: ref.read(voiceCaptureConfigProvider),
        onSpeechStart: () {
          if (_isCurrentCall(generation) &&
              state.phase == VoiceCallPhase.listening) {
            startCapturingSpeech();
          }
        },
        onSpeechEnded: () {
          if (_isCurrentCall(generation) &&
              state.phase == VoiceCallPhase.listening) {
            endpointUtterance();
          }
        },
        onAudioChunk: (chunk) async {
          if (_isCurrentCall(generation)) {
            session.sendAudioChunk(chunk);
          }
        },
      );
    } on Object {
      if (_isCurrentCall(generation)) {
        fail('Could not stream voice audio.');
      }
      unawaited(session.endSession());
      return;
    }

    if (!_isCurrentCall(generation) || !state.isCallActive) {
      unawaited(session.endSession());
      return;
    }
    if (!capturedAudio) {
      if (state.phase == VoiceCallPhase.thinking ||
          state.phase == VoiceCallPhase.speaking) {
        return;
      }
      unawaited(session.endSession());
      resumeListening();
      return;
    }

    endpointUtterance();
    session.endUtterance();
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
      if (state.phase == VoiceCallPhase.listening) {
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
      startThinking();
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

      state = state.copyWith(
        conversationId: response.conversationId,
        currentTranscript: response.transcript,
        clearError: true,
      );
      ref
          .read(chatProvider.notifier)
          .applyBackendMessages(
            conversationId: response.conversationId,
            messages: response.messages,
            fallbackAssistantResponse: response.responseText,
          );

      startThinking(finalTranscript: response.transcript);
      startSpeaking(response.responseText);
      _startBargeInMonitoring(generation);
      await _playbackService.playBase64Audio(
        response.audioBase64,
        contentType: response.audioContentType,
        onComplete: () {
          if (_isCurrentCall(generation)) {
            _stopBargeInMonitoring();
            completeSpeaking();
          }
        },
        onError: (message) {
          if (_isCurrentCall(generation)) {
            _stopBargeInMonitoring();
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

  Future<void> _handleStreamingEvents(
    StreamingVoiceSession session,
    int generation,
  ) async {
    var assistantText = '';
    var responseAudioStarted = false;
    void beginStreamingAudioIfNeeded() {
      if (responseAudioStarted) {
        return;
      }
      responseAudioStarted = true;
      _streamingPlaybackQueue.beginResponse();
    }

    StreamingAudioPlaybackCallbacks playbackCallbacks() {
      return StreamingAudioPlaybackCallbacks(
        onChunkStarted: (_) {
          if (_isCurrentCall(generation)) {
            startSpeaking(assistantText);
            _startBargeInMonitoring(generation);
          }
        },
        onQueueDrained: () {
          _stopBargeInMonitoring();
          if (_isCurrentCall(generation) &&
              state.phase == VoiceCallPhase.speaking) {
            completeSpeaking();
          }
        },
        onError: (message) {
          _stopBargeInMonitoring();
          if (_isCurrentCall(generation)) {
            fail(message);
          }
        },
      );
    }

    try {
      await for (final event in session.events) {
        if (!_isCurrentCall(generation) || !state.isCallActive) {
          return;
        }

        switch (event.name) {
          case 'session.started':
            break;
          case 'transcript.partial':
            updateTranscript(event.transcript ?? state.currentTranscript);
          case 'transcript.final':
            if (event.speechFinal) {
              assistantText = '';
              responseAudioStarted = false;
              startThinking(finalTranscript: event.transcript);
              unawaited(_activeStreamingCaptureService?.cancel());
            } else {
              updateTranscript(
                event.transcript ?? state.currentTranscript,
                isFinal: true,
              );
            }
          case 'conversation.updated':
            state = state.copyWith(
              conversationId: event.conversationId,
              clearError: true,
            );
          case 'assistant.started':
            unawaited(_activeStreamingCaptureService?.cancel());
            if (state.phase != VoiceCallPhase.thinking) {
              startThinking(finalTranscript: state.currentTranscript);
            }
            beginStreamingAudioIfNeeded();
          case 'assistant.token':
            assistantText += event.token ?? '';
            state = state.copyWith(lastAssistantResponse: assistantText);
          case 'assistant.audio_chunk':
            final audioBase64 = event.audioBase64;
            if (audioBase64 == null || audioBase64.isEmpty) {
              break;
            }
            beginStreamingAudioIfNeeded();
            _streamingPlaybackQueue.enqueue(
              StreamingAudioChunk(
                audioBase64: audioBase64,
                contentType: event.audioContentType,
                text: event.data['text'] as String? ?? '',
              ),
              callbacks: playbackCallbacks(),
            );
          case 'messages.updated':
            final rawMessages = event.data['messages'];
            if (event.conversationId != null && rawMessages is List) {
              final messages = rawMessages
                  .whereType<Map<String, dynamic>>()
                  .map(ChatApiMessage.fromJson)
                  .toList(growable: false);
              ref
                  .read(chatProvider.notifier)
                  .applyBackendMessages(
                    conversationId: event.conversationId!,
                    messages: messages,
                    fallbackAssistantResponse: assistantText,
                  );
            }
          case 'assistant.done':
            beginStreamingAudioIfNeeded();
            if (event.conversationId != null) {
              state = state.copyWith(
                conversationId: event.conversationId,
                lastAssistantResponse: event.responseText ?? assistantText,
                clearError: true,
              );
            }
            _streamingPlaybackQueue.finishResponse(
              callbacks: playbackCallbacks(),
            );
            await _streamingPlaybackQueue.waitUntilIdle();
            if (_isCurrentCall(generation) &&
                state.isCallActive &&
                state.phase != VoiceCallPhase.speaking &&
                state.phase != VoiceCallPhase.listening &&
                !state.isMuted) {
              resumeListening();
            }
            unawaited(session.endSession());
            return;
          case 'session.ended':
            return;
          case 'session.interrupted':
            break;
        }
      }
    } on StreamingVoiceApiException catch (error) {
      if (_isCurrentCall(generation)) {
        fail(error.message);
      }
    } on Object {
      if (_isCurrentCall(generation)) {
        fail('Rex voice stream failed.');
      }
    } finally {
      if (identical(_activeStreamingSession, session)) {
        _activeStreamingSession = null;
      }
    }
  }

  bool _isCurrentCall(int generation) => generation == _callGeneration;

  void _startBargeInMonitoring(int generation) {
    if (_isBargeInMonitoring ||
        !_isCurrentCall(generation) ||
        state.phase != VoiceCallPhase.speaking ||
        state.isMuted) {
      return;
    }

    _isBargeInMonitoring = true;
    unawaited(
      _bargeInDetectionService
          .start(
            config: ref.read(voiceCaptureConfigProvider),
            onBargeIn: () {
              if (_isCurrentCall(generation) &&
                  state.phase == VoiceCallPhase.speaking &&
                  !state.isMuted) {
                interruptAndListen();
              }
            },
          )
          .catchError((Object _) {
            _isBargeInMonitoring = false;
          }),
    );
  }

  void _stopBargeInMonitoring() {
    if (!_isBargeInMonitoring && _activeBargeInDetectionService == null) {
      return;
    }
    _isBargeInMonitoring = false;
    unawaited(_bargeInDetectionService.stop());
  }

  void _clearVisibleTranscript() {
    _finalTranscriptBuffer = '';
    _partialTranscriptBuffer = '';
  }

  void _appendFinalTranscript(String? transcript) {
    final next = transcript?.trim() ?? '';
    if (next.isEmpty) {
      return;
    }

    final previousPartial = _partialTranscriptBuffer.trim();
    _partialTranscriptBuffer = '';
    if (previousPartial.isNotEmpty && !next.contains(previousPartial)) {
      _appendTranscriptSegment(previousPartial);
    }
    _appendTranscriptSegment(next);
  }

  void _appendTranscriptSegment(String next) {
    if (_finalTranscriptBuffer.isEmpty) {
      _finalTranscriptBuffer = next;
      return;
    }
    if (_finalTranscriptBuffer == next ||
        _finalTranscriptBuffer.endsWith(next)) {
      return;
    }
    if (next.startsWith(_finalTranscriptBuffer)) {
      _finalTranscriptBuffer = next;
      return;
    }
    _finalTranscriptBuffer = '$_finalTranscriptBuffer $next';
  }

  String _visibleTranscript() {
    final finalText = _finalTranscriptBuffer.trim();
    final partialText = _partialTranscriptBuffer.trim();
    if (finalText.isEmpty) {
      return partialText;
    }
    if (partialText.isEmpty ||
        finalText == partialText ||
        finalText.endsWith(partialText)) {
      return finalText;
    }
    if (partialText.startsWith(finalText)) {
      return partialText;
    }
    return '$finalText $partialText';
  }

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

  StreamingAudioCaptureService get _streamingCaptureService {
    final existingService = _activeStreamingCaptureService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(streamingAudioCaptureServiceProvider);
    _activeStreamingCaptureService = service;
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

  StreamingAudioPlaybackQueue get _streamingPlaybackQueue {
    final existingQueue = _activeStreamingPlaybackQueue;
    if (existingQueue != null) {
      return existingQueue;
    }
    final queue = ref.read(streamingAudioPlaybackQueueProvider);
    _activeStreamingPlaybackQueue = queue;
    return queue;
  }

  BargeInDetectionService get _bargeInDetectionService {
    final existingService = _activeBargeInDetectionService;
    if (existingService != null) {
      return existingService;
    }
    final service = ref.read(bargeInDetectionServiceProvider);
    _activeBargeInDetectionService = service;
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
