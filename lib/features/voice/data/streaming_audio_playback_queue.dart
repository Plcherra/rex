import 'dart:async';
import 'dart:collection';

import 'package:rex/features/voice/data/audio_playback_service.dart';

class StreamingAudioChunk {
  const StreamingAudioChunk({
    required this.audioBase64,
    required this.contentType,
    this.text = '',
  });

  final String audioBase64;
  final String contentType;
  final String text;
}

typedef StreamingAudioChunkCallback = void Function(StreamingAudioChunk chunk);
typedef StreamingAudioQueueCallback = void Function();
typedef StreamingAudioQueueErrorCallback = void Function(String message);

class StreamingAudioPlaybackCallbacks {
  const StreamingAudioPlaybackCallbacks({
    required this.onChunkStarted,
    required this.onQueueDrained,
    required this.onError,
  });

  final StreamingAudioChunkCallback onChunkStarted;
  final StreamingAudioQueueCallback onQueueDrained;
  final StreamingAudioQueueErrorCallback onError;
}

class StreamingAudioPlaybackQueue {
  StreamingAudioPlaybackQueue(this._playbackService);

  final AudioPlaybackService _playbackService;
  final Queue<StreamingAudioChunk> _chunks = Queue<StreamingAudioChunk>();

  var _generation = 0;
  var _isPlaying = false;
  var _acceptingChunks = false;
  Completer<void>? _idleCompleter;

  bool get isPlaying => _isPlaying;

  bool get isIdle => !_isPlaying && _chunks.isEmpty;

  void beginResponse() {
    _generation++;
    _chunks.clear();
    _isPlaying = false;
    _acceptingChunks = true;
    _idleCompleter = Completer<void>();
  }

  void enqueue(
    StreamingAudioChunk chunk, {
    required StreamingAudioPlaybackCallbacks callbacks,
  }) {
    if (!_acceptingChunks || chunk.audioBase64.isEmpty) {
      return;
    }
    _chunks.add(chunk);
    _playNextIfNeeded(_generation, callbacks);
  }

  void finishResponse({required StreamingAudioPlaybackCallbacks callbacks}) {
    _acceptingChunks = false;
    if (isIdle) {
      _completeIdle();
      callbacks.onQueueDrained();
    }
  }

  Future<void> waitUntilIdle() async {
    final idleCompleter = _idleCompleter;
    if (idleCompleter == null || idleCompleter.isCompleted) {
      return;
    }
    await idleCompleter.future;
  }

  Future<void> cancel() async {
    _generation++;
    _chunks.clear();
    _isPlaying = false;
    _acceptingChunks = false;
    _completeIdle();
    await _playbackService.stop();
  }

  void _playNextIfNeeded(
    int generation,
    StreamingAudioPlaybackCallbacks callbacks,
  ) {
    if (_isPlaying || generation != _generation) {
      return;
    }
    _playNext(generation, callbacks);
  }

  void _playNext(int generation, StreamingAudioPlaybackCallbacks callbacks) {
    if (generation != _generation) {
      return;
    }
    if (_chunks.isEmpty) {
      _isPlaying = false;
      if (!_acceptingChunks) {
        _completeIdle();
        callbacks.onQueueDrained();
      }
      return;
    }

    final chunk = _chunks.removeFirst();
    _isPlaying = true;
    callbacks.onChunkStarted(chunk);
    unawaited(
      _playbackService
          .playBase64Audio(
            chunk.audioBase64,
            contentType: chunk.contentType,
            onComplete: () {
              if (generation != _generation) {
                return;
              }
              _isPlaying = false;
              _playNext(generation, callbacks);
            },
            onError: (message) {
              if (generation != _generation) {
                return;
              }
              _chunks.clear();
              _isPlaying = false;
              _acceptingChunks = false;
              _completeIdle();
              callbacks.onError(message);
            },
          )
          .catchError((Object _) {
            if (generation != _generation) {
              return;
            }
            _chunks.clear();
            _isPlaying = false;
            _acceptingChunks = false;
            _completeIdle();
            callbacks.onError('Voice playback failed.');
          }),
    );
  }

  void _completeIdle() {
    final idleCompleter = _idleCompleter;
    if (idleCompleter != null && !idleCompleter.isCompleted) {
      idleCompleter.complete();
    }
  }
}
