import 'package:flutter/services.dart';

import 'package:rex/core/config/app_config.dart';

class NativeVoiceSessionConfig {
  const NativeVoiceSessionConfig({
    this.backendBaseUrl = AppConfig.backendBaseUrl,
    this.conversationId,
    this.sampleRate = 16000,
    this.inputMimeType = 'audio/linear16',
  });

  final String backendBaseUrl;
  final String? conversationId;
  final int sampleRate;
  final String inputMimeType;

  Map<String, Object> toJson() {
    final payload = <String, Object>{
      'backendBaseUrl': backendBaseUrl,
      'sampleRate': sampleRate,
      'inputMimeType': inputMimeType,
    };
    final conversationId = this.conversationId;
    if (conversationId != null && conversationId.isNotEmpty) {
      payload['conversationId'] = conversationId;
    }
    return payload;
  }
}

class NativeVoiceEvent {
  const NativeVoiceEvent(this.name, this.data);

  factory NativeVoiceEvent.fromMap(Map<dynamic, dynamic> raw) {
    final data = Map<String, dynamic>.from(raw);
    return NativeVoiceEvent(data['event'] as String? ?? 'unknown', data);
  }

  final String name;
  final Map<String, dynamic> data;

  String? get transcript => data['transcript'] as String?;

  String? get token => data['token'] as String?;

  String? get conversationId => data['conversation_id'] as String?;

  String? get responseText => data['response_text'] as String?;

  String? get detail => data['detail'] as String?;
}

abstract class NativeVoiceSessionService {
  Stream<NativeVoiceEvent> get events;

  Future<void> startSession(NativeVoiceSessionConfig config);

  Future<void> stopSession();

  Future<void> interrupt();

  Future<void> setMuted(bool isMuted);

  Future<void> setForegroundState(bool isForeground);
}

class MethodChannelNativeVoiceSessionService
    implements NativeVoiceSessionService {
  MethodChannelNativeVoiceSessionService({
    MethodChannel? methodChannel,
    EventChannel? eventChannel,
  }) : _methodChannel =
           methodChannel ?? const MethodChannel('rex/native_voice'),
       _eventChannel =
           eventChannel ?? const EventChannel('rex/native_voice_events');

  final MethodChannel _methodChannel;
  final EventChannel _eventChannel;

  @override
  late final Stream<NativeVoiceEvent> events = _eventChannel
      .receiveBroadcastStream()
      .where((event) => event is Map)
      .map((event) => NativeVoiceEvent.fromMap(event as Map<dynamic, dynamic>));

  @override
  Future<void> startSession(NativeVoiceSessionConfig config) async {
    await _invokeIfAvailable('startSession', config.toJson());
  }

  @override
  Future<void> stopSession() async {
    await _invokeIfAvailable('stopSession');
  }

  @override
  Future<void> interrupt() async {
    await _invokeIfAvailable('interrupt');
  }

  @override
  Future<void> setMuted(bool isMuted) async {
    await _invokeIfAvailable('setMuted', <String, Object>{'isMuted': isMuted});
  }

  @override
  Future<void> setForegroundState(bool isForeground) async {
    await _invokeIfAvailable('setForegroundState', <String, Object>{
      'isForeground': isForeground,
    });
  }

  Future<void> _invokeIfAvailable(String method, [Object? arguments]) async {
    try {
      await _methodChannel.invokeMethod<void>(method, arguments);
    } on MissingPluginException {
      // Desktop, web, and tests can run without the iOS native voice bridge.
    }
  }
}
