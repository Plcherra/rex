import 'dart:async';

import 'package:audio_session/audio_session.dart';
import 'package:flutter/services.dart';

typedef VoiceAudioInterruptionCallback = void Function(String message);

abstract class VoiceAudioSessionService {
  Future<void> configureForVoiceTurn();

  Future<void> setActive(bool active);

  StreamSubscription<void> listenForNoisyAudio(
    VoiceAudioInterruptionCallback onInterrupted,
  );

  StreamSubscription<AudioInterruptionEvent> listenForInterruptions(
    VoiceAudioInterruptionCallback onInterrupted,
  );
}

class PackageVoiceAudioSessionService implements VoiceAudioSessionService {
  AudioSession? _session;

  @override
  Future<void> configureForVoiceTurn() async {
    try {
      final session = await _audioSession();
      await session.configure(
        AudioSessionConfiguration(
          avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
          avAudioSessionCategoryOptions:
              AVAudioSessionCategoryOptions.allowBluetooth |
              AVAudioSessionCategoryOptions.allowBluetoothA2dp |
              AVAudioSessionCategoryOptions.defaultToSpeaker,
          avAudioSessionMode: AVAudioSessionMode.voiceChat,
          androidAudioAttributes: const AndroidAudioAttributes(
            contentType: AndroidAudioContentType.speech,
            usage: AndroidAudioUsage.voiceCommunication,
          ),
          androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
          androidWillPauseWhenDucked: true,
        ),
      );
      await session.setActive(true);
    } on MissingPluginException {
      // Tests and unsupported platforms can run without native audio sessions.
    } on Object {
      // Audio-session setup should improve reliability, not block voice mode.
    }
  }

  @override
  Future<void> setActive(bool active) async {
    try {
      final session = await _audioSession();
      await session.setActive(active);
    } on MissingPluginException {
      // Tests and unsupported platforms can run without native audio sessions.
    } on Object {
      // Audio-session cleanup should never break controller disposal.
    }
  }

  @override
  StreamSubscription<void> listenForNoisyAudio(
    VoiceAudioInterruptionCallback onInterrupted,
  ) {
    final session = _session;
    if (session == null) {
      return const Stream<void>.empty().listen((_) {});
    }
    try {
      return session.becomingNoisyEventStream.listen((_) {
        onInterrupted(
          'Audio route changed. Restart the voice turn if Rex stopped hearing you.',
        );
      });
    } on Object {
      return const Stream<void>.empty().listen((_) {});
    }
  }

  @override
  StreamSubscription<AudioInterruptionEvent> listenForInterruptions(
    VoiceAudioInterruptionCallback onInterrupted,
  ) {
    final session = _session;
    if (session == null) {
      return const Stream<AudioInterruptionEvent>.empty().listen((_) {});
    }
    try {
      return session.interruptionEventStream.listen((event) {
        if (event.begin && event.type != AudioInterruptionType.duck) {
          onInterrupted(
            'Audio was interrupted. Restart the voice turn when you are ready.',
          );
        }
      });
    } on Object {
      return const Stream<AudioInterruptionEvent>.empty().listen((_) {});
    }
  }

  Future<AudioSession> _audioSession() async {
    final existing = _session;
    if (existing != null) {
      return existing;
    }
    final session = await AudioSession.instance;
    _session = session;
    return session;
  }
}
