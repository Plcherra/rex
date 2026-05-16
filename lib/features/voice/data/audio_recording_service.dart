import 'dart:io';

import 'package:cross_file/cross_file.dart';
import 'package:record/record.dart';

class RecordedVoiceAudio {
  const RecordedVoiceAudio({required this.file, required this.inputMimeType});

  final XFile file;
  final String inputMimeType;
}

abstract class AudioRecordingService {
  Future<void> startRecording();

  Future<RecordedVoiceAudio?> stopRecording();

  Future<void> cancelRecording();
}

class PackageAudioRecordingService implements AudioRecordingService {
  PackageAudioRecordingService({AudioRecorder? recorder})
    : _recorder = recorder ?? AudioRecorder();

  final AudioRecorder _recorder;
  String? _recordingPath;

  @override
  Future<void> startRecording() async {
    final tempDirectory = await Directory.systemTemp.createTemp('rex_voice_');
    final path =
        '${tempDirectory.path}/voice-${DateTime.now().microsecondsSinceEpoch}.m4a';
    _recordingPath = path;
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.aacLc,
        bitRate: 64000,
        sampleRate: 16000,
      ),
      path: path,
    );
  }

  @override
  Future<RecordedVoiceAudio?> stopRecording() async {
    final path = await _recorder.stop() ?? _recordingPath;
    _recordingPath = null;
    if (path == null || path.trim().isEmpty) {
      return null;
    }

    return RecordedVoiceAudio(
      file: XFile(path, name: 'rex-voice.m4a', mimeType: 'audio/mp4'),
      inputMimeType: 'audio/mp4',
    );
  }

  @override
  Future<void> cancelRecording() async {
    await _recorder.cancel();
    _recordingPath = null;
  }
}
