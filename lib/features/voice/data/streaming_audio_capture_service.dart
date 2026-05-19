import 'dart:async';
import 'dart:math';
import 'dart:typed_data';

import 'package:record/record.dart';

import 'package:rex/features/voice/data/audio_capture_service.dart';

typedef AudioChunkCallback = Future<void> Function(Uint8List chunk);
typedef SpeechEndCallback = void Function();
typedef BargeInCallback = void Function();

abstract class StreamingAudioCaptureService {
  Future<bool> streamUtterance({
    required VoiceCaptureConfig config,
    required SpeechStartCallback onSpeechStart,
    required SpeechEndCallback onSpeechEnded,
    required AudioChunkCallback onAudioChunk,
  });

  Future<void> cancel();
}

abstract class BargeInDetectionService {
  Future<void> start({
    required VoiceCaptureConfig config,
    required BargeInCallback onBargeIn,
  });

  Future<void> stop();
}

class PackageBargeInDetectionService implements BargeInDetectionService {
  static const _bargeInGracePeriod = Duration(milliseconds: 800);
  static const _bargeInMinimumSpeechDuration = Duration(milliseconds: 260);
  static const _bargeInSpeechThresholdDb = -34.0;

  PackageBargeInDetectionService({
    AudioRecorder? recorder,
    DateTime Function()? now,
  }) : _recorder = recorder ?? AudioRecorder(),
       _now = now ?? DateTime.now;

  final AudioRecorder _recorder;
  final DateTime Function() _now;
  StreamSubscription<Uint8List>? _streamSubscription;
  DateTime? _startedAt;
  DateTime? _speechStartedAt;
  var _notified = false;

  @override
  Future<void> start({
    required VoiceCaptureConfig config,
    required BargeInCallback onBargeIn,
  }) async {
    await stop();
    _startedAt = _now();
    _speechStartedAt = null;
    _notified = false;

    final stream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      ),
    );

    _streamSubscription = stream.listen(
      (chunk) {
        if (_notified) {
          return;
        }

        final startedAt = _startedAt;
        final now = _now();
        if (startedAt == null ||
            now.difference(startedAt) < _bargeInGracePeriod) {
          return;
        }

        final currentDb = _pcm16Decibels(chunk);
        if (currentDb < _bargeInSpeechThresholdDb) {
          _speechStartedAt = null;
          return;
        }

        _speechStartedAt ??= now;
        if (now.difference(_speechStartedAt!) >=
            _bargeInMinimumSpeechDuration) {
          _notified = true;
          onBargeIn();
          unawaited(stop());
        }
      },
      onError: (_) {
        unawaited(stop());
      },
      cancelOnError: true,
    );
  }

  @override
  Future<void> stop() async {
    await _streamSubscription?.cancel();
    _streamSubscription = null;
    _startedAt = null;
    _speechStartedAt = null;
    _notified = false;
    try {
      await _recorder.cancel();
    } on Object {
      // The recorder may already be stopped.
    }
  }

  double _pcm16Decibels(Uint8List chunk) {
    if (chunk.length < 2) {
      return -160;
    }

    var sumSquares = 0.0;
    var sampleCount = 0;
    final byteData = ByteData.sublistView(chunk);
    for (var offset = 0; offset + 1 < chunk.length; offset += 2) {
      final sample = byteData.getInt16(offset, Endian.little) / 32768.0;
      sumSquares += sample * sample;
      sampleCount++;
    }
    if (sampleCount == 0 || sumSquares == 0) {
      return -160;
    }

    final rms = sqrt(sumSquares / sampleCount);
    return 20 * log(rms) / ln10;
  }
}

class PackageStreamingAudioCaptureService
    implements StreamingAudioCaptureService {
  static const _minimumStreamingSilenceAfterSpeech = Duration(
    milliseconds: 3000,
  );
  static const _minimumStreamingSpeechDuration = Duration(milliseconds: 500);
  static const _streamingSpeechStartThresholdDb = -46.0;
  static const _streamingSilenceThresholdDb = -52.0;

  PackageStreamingAudioCaptureService({
    AudioRecorder? recorder,
    DateTime Function()? now,
  }) : _recorder = recorder ?? AudioRecorder(),
       _now = now ?? DateTime.now;

  final AudioRecorder _recorder;
  final DateTime Function() _now;
  StreamSubscription<Uint8List>? _streamSubscription;
  Completer<bool>? _captureCompleter;
  Timer? _noSpeechTimer;
  Timer? _maxDurationTimer;

  @override
  Future<bool> streamUtterance({
    required VoiceCaptureConfig config,
    required SpeechStartCallback onSpeechStart,
    required SpeechEndCallback onSpeechEnded,
    required AudioChunkCallback onAudioChunk,
  }) async {
    await cancel();
    final endpointConfig = _streamingEndpointConfig(config);
    final detector = VoiceEndpointDetector(
      config: endpointConfig,
      startedAt: _now(),
    );
    _captureCompleter = Completer<bool>();
    var speechEndedNotified = false;

    final stream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      ),
    );

    _streamSubscription = stream.listen(
      (chunk) {
        unawaited(onAudioChunk(chunk));
        final update = detector.addAmplitude(
          currentDb: _pcm16Decibels(chunk),
          now: _now(),
        );
        if (update.speechStarted) {
          onSpeechStart();
        }
        if (update.endpointReached && !speechEndedNotified) {
          speechEndedNotified = true;
          onSpeechEnded();
        }
        if (update.endpointReached || update.maxDurationReached) {
          unawaited(_complete(keepAudio: detector.hasSpeech));
        } else if (update.noSpeechTimedOut) {
          unawaited(_complete(keepAudio: false));
        }
      },
      onError: (_) {
        unawaited(_complete(keepAudio: false));
      },
      cancelOnError: true,
    );

    _noSpeechTimer = Timer(endpointConfig.noSpeechTimeout, () {
      if (!detector.hasSpeech) {
        unawaited(_complete(keepAudio: false));
      }
    });
    _maxDurationTimer = Timer(endpointConfig.maxUtteranceDuration, () {
      unawaited(_complete(keepAudio: detector.hasSpeech));
    });

    return _captureCompleter!.future;
  }

  @override
  Future<void> cancel() async {
    _noSpeechTimer?.cancel();
    _noSpeechTimer = null;
    _maxDurationTimer?.cancel();
    _maxDurationTimer = null;
    await _streamSubscription?.cancel();
    _streamSubscription = null;
    if (_captureCompleter != null && !_captureCompleter!.isCompleted) {
      _captureCompleter!.complete(false);
    }
    _captureCompleter = null;
    try {
      await _recorder.cancel();
    } on Object {
      // The recorder may already be stopped.
    }
  }

  Future<void> _complete({required bool keepAudio}) async {
    final completer = _captureCompleter;
    if (completer == null || completer.isCompleted) {
      return;
    }
    _noSpeechTimer?.cancel();
    _noSpeechTimer = null;
    _maxDurationTimer?.cancel();
    _maxDurationTimer = null;
    await _streamSubscription?.cancel();
    _streamSubscription = null;
    try {
      await _recorder.stop();
    } on Object {
      // Treat native stop failures as an empty capture.
    }
    completer.complete(keepAudio);
  }

  VoiceCaptureConfig _streamingEndpointConfig(VoiceCaptureConfig config) {
    // Live PCM chunks are bursty on mobile. Keep streaming endpointing more
    // tolerant so a short pause or soft word does not prematurely end a turn.
    return VoiceCaptureConfig(
      amplitudeInterval: config.amplitudeInterval,
      speechStartThresholdDb: min(
        config.speechStartThresholdDb,
        _streamingSpeechStartThresholdDb,
      ),
      silenceThresholdDb: min(
        config.silenceThresholdDb,
        _streamingSilenceThresholdDb,
      ),
      silenceAfterSpeech: _longerDuration(
        config.silenceAfterSpeech,
        _minimumStreamingSilenceAfterSpeech,
      ),
      noSpeechTimeout: config.noSpeechTimeout,
      maxUtteranceDuration: config.maxUtteranceDuration,
      minSpeechDuration: _longerDuration(
        config.minSpeechDuration,
        _minimumStreamingSpeechDuration,
      ),
    );
  }

  Duration _longerDuration(Duration value, Duration minimum) {
    return value.compareTo(minimum) >= 0 ? value : minimum;
  }

  double _pcm16Decibels(Uint8List chunk) {
    if (chunk.length < 2) {
      return -160;
    }

    var sumSquares = 0.0;
    var sampleCount = 0;
    final byteData = ByteData.sublistView(chunk);
    for (var offset = 0; offset + 1 < chunk.length; offset += 2) {
      final sample = byteData.getInt16(offset, Endian.little) / 32768.0;
      sumSquares += sample * sample;
      sampleCount++;
    }
    if (sampleCount == 0 || sumSquares == 0) {
      return -160;
    }

    final rms = sqrt(sumSquares / sampleCount);
    return 20 * log(rms) / ln10;
  }
}
