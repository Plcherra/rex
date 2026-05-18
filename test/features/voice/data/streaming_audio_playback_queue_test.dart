import 'package:flutter_test/flutter_test.dart';
import 'package:rex/features/voice/data/audio_playback_service.dart';
import 'package:rex/features/voice/data/streaming_audio_playback_queue.dart';

void main() {
  test('StreamingAudioPlaybackQueue plays chunks in order', () async {
    final playback = _FakeAudioPlaybackService();
    final queue = StreamingAudioPlaybackQueue(playback);
    final started = <String>[];
    var drained = false;

    final callbacks = StreamingAudioPlaybackCallbacks(
      onChunkStarted: (chunk) => started.add(chunk.text),
      onQueueDrained: () => drained = true,
      onError: fail,
    );

    queue.beginResponse();
    queue.enqueue(
      const StreamingAudioChunk(
        audioBase64: 'chunk-1',
        contentType: 'audio/mpeg',
        text: 'first',
      ),
      callbacks: callbacks,
    );
    queue.enqueue(
      const StreamingAudioChunk(
        audioBase64: 'chunk-2',
        contentType: 'audio/mpeg',
        text: 'second',
      ),
      callbacks: callbacks,
    );
    queue.finishResponse(callbacks: callbacks);
    await pumpEventQueue();

    expect(started, ['first']);
    expect(playback.playedAudioBase64, ['chunk-1']);
    expect(drained, false);

    playback.completeCurrent();
    await pumpEventQueue();
    expect(started, ['first', 'second']);
    expect(playback.playedAudioBase64, ['chunk-1', 'chunk-2']);

    playback.completeCurrent();
    await queue.waitUntilIdle();
    expect(drained, true);
    expect(queue.isIdle, true);
  });

  test('StreamingAudioPlaybackQueue cancels stale queued audio', () async {
    final playback = _FakeAudioPlaybackService();
    final queue = StreamingAudioPlaybackQueue(playback);
    final started = <String>[];

    final callbacks = StreamingAudioPlaybackCallbacks(
      onChunkStarted: (chunk) => started.add(chunk.text),
      onQueueDrained: () {},
      onError: fail,
    );

    queue.beginResponse();
    queue.enqueue(
      const StreamingAudioChunk(
        audioBase64: 'chunk-1',
        contentType: 'audio/mpeg',
        text: 'first',
      ),
      callbacks: callbacks,
    );
    queue.enqueue(
      const StreamingAudioChunk(
        audioBase64: 'chunk-2',
        contentType: 'audio/mpeg',
        text: 'second',
      ),
      callbacks: callbacks,
    );
    await pumpEventQueue();

    await queue.cancel();
    playback.completeCurrent();
    await pumpEventQueue();

    expect(started, ['first']);
    expect(playback.stopCount, 1);
    expect(queue.isIdle, true);
  });
}

class _FakeAudioPlaybackService implements AudioPlaybackService {
  AudioPlaybackCompleteCallback? _onComplete;
  final playedAudioBase64 = <String>[];
  var stopCount = 0;

  @override
  Future<void> playBase64Audio(
    String audioBase64, {
    required String contentType,
    required AudioPlaybackCompleteCallback onComplete,
    required AudioPlaybackErrorCallback onError,
  }) async {
    playedAudioBase64.add(audioBase64);
    _onComplete = onComplete;
  }

  @override
  Future<void> pause() async {}

  @override
  Future<void> stop() async {
    stopCount++;
  }

  void completeCurrent() {
    _onComplete?.call();
  }
}
