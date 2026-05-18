import 'dart:async';
import 'dart:math';
import 'dart:typed_data';

import 'package:record/record.dart';

import 'package:rex/features/voice/data/audio_capture_service.dart';

typedef AudioChunkCallback = Future<void> Function(Uint8List chunk);

abstract class StreamingAudioCaptureService {
  Future<bool> streamUtterance({
    required VoiceCaptureConfig config,
    required SpeechStartCallback onSpeechStart,
    required AudioChunkCallback onAudioChunk,
  });

  Future<void> cancel();
}

class PackageStreamingAudioCaptureService
    implements StreamingAudioCaptureService {
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
    required AudioChunkCallback onAudioChunk,
  }) async {
    await cancel();
    final detector = VoiceEndpointDetector(config: config, startedAt: _now());
    _captureCompleter = Completer<bool>();

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

    _noSpeechTimer = Timer(config.noSpeechTimeout, () {
      if (!detector.hasSpeech) {
        unawaited(_complete(keepAudio: false));
      }
    });
    _maxDurationTimer = Timer(config.maxUtteranceDuration, () {
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
