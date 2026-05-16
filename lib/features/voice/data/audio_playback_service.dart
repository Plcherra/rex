import 'dart:convert';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';

typedef AudioPlaybackCompleteCallback = void Function();
typedef AudioPlaybackErrorCallback = void Function(String message);

abstract class AudioPlaybackService {
  Future<void> playBase64Audio(
    String audioBase64, {
    required String contentType,
    required AudioPlaybackCompleteCallback onComplete,
    required AudioPlaybackErrorCallback onError,
  });

  Future<void> stop();

  Future<void> pause();
}

class PackageAudioPlaybackService implements AudioPlaybackService {
  PackageAudioPlaybackService({AudioPlayer? audioPlayer})
    : _audioPlayer = audioPlayer ?? AudioPlayer();

  final AudioPlayer _audioPlayer;

  @override
  Future<void> playBase64Audio(
    String audioBase64, {
    required String contentType,
    required AudioPlaybackCompleteCallback onComplete,
    required AudioPlaybackErrorCallback onError,
  }) async {
    final Uint8List audioBytes;
    try {
      audioBytes = base64Decode(audioBase64);
    } on FormatException {
      onError('Rex returned invalid voice audio.');
      return;
    }
    if (audioBytes.isEmpty) {
      onError('Rex returned empty voice audio.');
      return;
    }

    try {
      await _audioPlayer.stop();
      _audioPlayer.onPlayerComplete.first.then((_) => onComplete());
      await _audioPlayer.play(BytesSource(audioBytes, mimeType: contentType));
    } catch (_) {
      onError('Voice playback failed.');
    }
  }

  @override
  Future<void> stop() async {
    await _audioPlayer.stop();
  }

  @override
  Future<void> pause() async {
    await _audioPlayer.pause();
  }
}
