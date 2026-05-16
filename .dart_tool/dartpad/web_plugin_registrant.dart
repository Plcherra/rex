// Flutter web plugin registrant file.
//
// Generated file. Do not edit.
//

// @dart = 2.13
// ignore_for_file: type=lint

import 'package:audio_session/audio_session_web.dart';
import 'package:audioplayers_web/audioplayers_web.dart';
import 'package:file_picker/_internal/file_picker_web.dart';
import 'package:flutter_tts/flutter_tts_web.dart';
import 'package:permission_handler_html/permission_handler_html.dart';
import 'package:record_web/record_web.dart';
import 'package:speech_to_text/speech_to_text_web.dart';
import 'package:flutter_web_plugins/flutter_web_plugins.dart';

void registerPlugins([final Registrar? pluginRegistrar]) {
  final Registrar registrar = pluginRegistrar ?? webPluginRegistrar;
  AudioSessionWeb.registerWith(registrar);
  AudioplayersPlugin.registerWith(registrar);
  FilePickerWeb.registerWith(registrar);
  FlutterTtsPlugin.registerWith(registrar);
  WebPermissionHandler.registerWith(registrar);
  RecordPluginWeb.registerWith(registrar);
  SpeechToTextPlugin.registerWith(registrar);
  registrar.registerMessageHandler();
}
