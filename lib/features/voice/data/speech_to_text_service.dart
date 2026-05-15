import 'package:speech_to_text/speech_recognition_error.dart' as stt;
import 'package:speech_to_text/speech_recognition_result.dart' as stt;
import 'package:speech_to_text/speech_to_text.dart' as stt;

typedef SpeechTranscriptCallback = void Function(String transcript);
typedef SpeechErrorCallback = void Function(String message);

abstract class SpeechToTextService {
  Future<bool> initialize({required SpeechErrorCallback onError});

  Future<void> startListening({
    required SpeechTranscriptCallback onPartialTranscript,
    required SpeechTranscriptCallback onFinalTranscript,
    required SpeechErrorCallback onError,
  });

  Future<void> stopListening();

  Future<void> cancel();
}

class PackageSpeechToTextService implements SpeechToTextService {
  PackageSpeechToTextService({stt.SpeechToText? speechToText})
    : _speechToText = speechToText ?? stt.SpeechToText();

  final stt.SpeechToText _speechToText;
  var _isInitialized = false;

  @override
  Future<bool> initialize({required SpeechErrorCallback onError}) async {
    if (_isInitialized) {
      return true;
    }

    final available = await _speechToText.initialize(
      onError: (stt.SpeechRecognitionError error) {
        onError(_formatError(error));
      },
    );
    _isInitialized = available;
    if (!available) {
      onError('Speech recognition is not available on this device.');
    }
    return available;
  }

  @override
  Future<void> startListening({
    required SpeechTranscriptCallback onPartialTranscript,
    required SpeechTranscriptCallback onFinalTranscript,
    required SpeechErrorCallback onError,
  }) async {
    if (!_isInitialized) {
      final available = await initialize(onError: onError);
      if (!available) {
        return;
      }
    }

    await _speechToText.listen(
      listenOptions: stt.SpeechListenOptions(
        listenMode: stt.ListenMode.dictation,
        partialResults: true,
        cancelOnError: true,
      ),
      onResult: (stt.SpeechRecognitionResult result) {
        final transcript = result.recognizedWords.trim();
        if (transcript.isEmpty) {
          return;
        }
        if (result.finalResult) {
          onFinalTranscript(transcript);
        } else {
          onPartialTranscript(transcript);
        }
      },
    );
  }

  @override
  Future<void> stopListening() async {
    await _speechToText.stop();
  }

  @override
  Future<void> cancel() async {
    await _speechToText.cancel();
  }

  String _formatError(stt.SpeechRecognitionError error) {
    final errorMessage = error.errorMsg.trim();
    if (errorMessage.isEmpty) {
      return 'Speech recognition failed.';
    }
    return switch (errorMessage) {
      'error_no_match' =>
        'I did not catch any audio. If you are using the iOS simulator, set Simulator > I/O > Audio Input to your Mac microphone and make sure macOS allows Simulator microphone access.',
      'error_speech_timeout' =>
        'I did not hear speech before the recognizer timed out. Try again closer to the microphone.',
      'error_permission' || 'error_speech_recognizer_disabled' =>
        'Speech recognition is blocked. Enable microphone and speech recognition access in Settings.',
      'error_network' || 'error_network_timeout' =>
        'Speech recognition could not reach Apple speech services. Check the simulator/device network and try again.',
      _ => errorMessage,
    };
  }
}
