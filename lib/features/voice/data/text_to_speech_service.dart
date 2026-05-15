import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

typedef TextToSpeechCompleteCallback = void Function();
typedef TextToSpeechErrorCallback = void Function(String message);

abstract class TextToSpeechService {
  Future<void> speak(
    String text, {
    required TextToSpeechCompleteCallback onComplete,
    required TextToSpeechErrorCallback onError,
  });

  Future<void> stop();

  Future<void> pause();
}

class PackageTextToSpeechService implements TextToSpeechService {
  PackageTextToSpeechService({FlutterTts? flutterTts})
    : _flutterTts = flutterTts ?? FlutterTts();

  final FlutterTts _flutterTts;
  var _defaultsConfigured = false;

  @override
  Future<void> speak(
    String text, {
    required TextToSpeechCompleteCallback onComplete,
    required TextToSpeechErrorCallback onError,
  }) async {
    final trimmedText = text.trim();
    if (trimmedText.isEmpty) {
      onComplete();
      return;
    }

    try {
      await _configureDefaults();
      _flutterTts.setCompletionHandler(onComplete);
      _flutterTts.setErrorHandler((dynamic message) {
        onError(_formatError(message));
      });
      await _flutterTts.speak(trimmedText, focus: true);
    } catch (_) {
      onError('Text-to-speech playback failed.');
    }
  }

  @override
  Future<void> stop() async {
    await _flutterTts.stop();
  }

  @override
  Future<void> pause() async {
    await _flutterTts.pause();
  }

  Future<void> _configureDefaults() async {
    if (_defaultsConfigured) {
      return;
    }

    await _flutterTts.awaitSpeakCompletion(false);
    await _flutterTts.setLanguage('en-US');
    await _flutterTts.setSpeechRate(0.52);
    await _flutterTts.setPitch(1.0);
    await _flutterTts.setVolume(1.0);

    if (defaultTargetPlatform == TargetPlatform.iOS) {
      await _flutterTts.setSharedInstance(true);
      await _flutterTts.setIosAudioCategory(
        IosTextToSpeechAudioCategory.playAndRecord,
        <IosTextToSpeechAudioCategoryOptions>[
          IosTextToSpeechAudioCategoryOptions.duckOthers,
          IosTextToSpeechAudioCategoryOptions.allowBluetooth,
          IosTextToSpeechAudioCategoryOptions.allowBluetoothA2DP,
          IosTextToSpeechAudioCategoryOptions.defaultToSpeaker,
        ],
        IosTextToSpeechAudioMode.spokenAudio,
      );
    }

    _defaultsConfigured = true;
  }

  String _formatError(dynamic message) {
    final errorMessage = message?.toString().trim();
    if (errorMessage == null || errorMessage.isEmpty) {
      return 'Text-to-speech playback failed.';
    }
    return errorMessage;
  }
}
