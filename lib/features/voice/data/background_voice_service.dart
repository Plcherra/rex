import 'package:flutter/services.dart';

abstract class BackgroundVoiceService {
  Future<void> start();

  Future<void> stop();
}

class MethodChannelBackgroundVoiceService implements BackgroundVoiceService {
  static const MethodChannel _channel = MethodChannel('rex/voice_background');

  @override
  Future<void> start() async {
    try {
      await _channel.invokeMethod<void>('start');
    } on MissingPluginException {
      // Desktop, web, and tests can run without the native background bridge.
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _channel.invokeMethod<void>('stop');
    } on MissingPluginException {
      // Desktop, web, and tests can run without the native background bridge.
    }
  }
}
