import Flutter
import Foundation

final class RexNativeVoiceBridge: NSObject, FlutterStreamHandler {
  static let methodChannelName = "rex/native_voice"
  static let eventChannelName = "rex/native_voice_events"

  private let methodChannel: FlutterMethodChannel
  private let eventChannel: FlutterEventChannel
  private let audioSession: RexNativeAudioSession
  private let audioCapture: RexNativeAudioCapture
  private let audioPlayback: RexNativeAudioPlayback
  private let voiceWebSocket: RexNativeVoiceWebSocket
  private var eventSink: FlutterEventSink?
  private var isSessionActive = false
  private var isMuted = false
  private var isForeground = true
  private var assistantDonePendingRestart = false

  init(messenger: FlutterBinaryMessenger) {
    audioSession = RexNativeAudioSession()
    audioCapture = RexNativeAudioCapture()
    audioPlayback = RexNativeAudioPlayback()
    voiceWebSocket = RexNativeVoiceWebSocket()
    methodChannel = FlutterMethodChannel(
      name: Self.methodChannelName,
      binaryMessenger: messenger
    )
    eventChannel = FlutterEventChannel(
      name: Self.eventChannelName,
      binaryMessenger: messenger
    )
    super.init()
    audioSession.onEvent = { [weak self] payload in
      self?.handleAudioSessionEvent(payload)
    }
    audioCapture.onEvent = { [weak self] payload in
      self?.handleCaptureEvent(payload)
    }
    audioCapture.onAudioChunk = { [weak self] data in
      self?.voiceWebSocket.sendAudioChunk(data)
      self?.emit([
        "event": "audio.chunk",
        "native": true,
        "byte_count": data.count
      ])
    }
    audioPlayback.onEvent = { [weak self] payload in
      self?.emit(payload)
    }
    audioPlayback.onDrained = { [weak self] in
      DispatchQueue.main.async {
        self?.restartCaptureAfterPlaybackIfReady()
      }
    }
    voiceWebSocket.onEvent = { [weak self] payload in
      self?.handleTransportEvent(payload)
    }
    methodChannel.setMethodCallHandler(handle)
    eventChannel.setStreamHandler(self)
  }

  func onListen(
    withArguments arguments: Any?,
    eventSink events: @escaping FlutterEventSink
  ) -> FlutterError? {
    eventSink = events
    return nil
  }

  func onCancel(withArguments arguments: Any?) -> FlutterError? {
    eventSink = nil
    return nil
  }

  private func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    switch call.method {
    case "startSession":
      do {
        try startSession(arguments: call.arguments)
        result(nil)
      } catch {
        emit([
          "event": "error",
          "native": true,
          "detail": "Could not activate iOS voice audio session.",
          "native_error": error.localizedDescription
        ])
        result(FlutterError(
          code: "audio_session_activation_failed",
          message: "Could not activate iOS voice audio session.",
          details: error.localizedDescription
        ))
      }
    case "stopSession":
      stopSession()
      result(nil)
    case "interrupt":
      interrupt()
      result(nil)
    case "setMuted":
      setMuted(arguments: call.arguments)
      result(nil)
    case "setForegroundState":
      setForegroundState(arguments: call.arguments)
      result(nil)
    default:
      result(FlutterMethodNotImplemented)
    }
  }

  deinit {
    audioPlayback.stop()
    audioCapture.stop()
    voiceWebSocket.stop(sendSessionEnd: false)
    audioSession.dispose()
  }

  private func startSession(arguments: Any?) throws {
    let payload = arguments as? [String: Any] ?? [:]
    let config = RexNativeVoiceWebSocketConfig(
      backendBaseURL: payload["backendBaseUrl"] as? String ?? "",
      conversationID: payload["conversationId"] as? String,
      sampleRate: payload["sampleRate"] as? Int ?? 16000,
      inputMimeType: payload["inputMimeType"] as? String ?? "audio/linear16"
    )
    assistantDonePendingRestart = false
    try audioSession.activate()
    do {
      try voiceWebSocket.start(config: config)
      try audioCapture.start()
    } catch {
      voiceWebSocket.stop(sendSessionEnd: false)
      audioSession.deactivate()
      throw error
    }
    isSessionActive = true
    emit(["event": "listening", "native": true])
  }

  private func stopSession() {
    guard isSessionActive else {
      assistantDonePendingRestart = false
      audioPlayback.stop()
      audioCapture.stop()
      voiceWebSocket.stop()
      audioSession.deactivate()
      emit(["event": "session.ended", "native": true])
      return
    }
    isSessionActive = false
    assistantDonePendingRestart = false
    audioPlayback.stop()
    audioCapture.stop()
    voiceWebSocket.stop()
    audioSession.deactivate()
    emit(["event": "session.ended", "native": true])
  }

  private func interrupt() {
    guard isSessionActive else {
      return
    }
    assistantDonePendingRestart = false
    audioPlayback.stop()
    audioCapture.stop()
    voiceWebSocket.interrupt()
    emit(["event": "session.interrupted", "native": true])
    restartCaptureAfterInterrupt()
  }

  private func setMuted(arguments: Any?) {
    let payload = arguments as? [String: Any] ?? [:]
    isMuted = payload["isMuted"] as? Bool ?? isMuted
    audioCapture.setMuted(isMuted)
    emit(["event": "muted.changed", "native": true, "is_muted": isMuted])
  }

  private func setForegroundState(arguments: Any?) {
    let payload = arguments as? [String: Any] ?? [:]
    isForeground = payload["isForeground"] as? Bool ?? isForeground
    emit([
      "event": "foreground.changed",
      "native": true,
      "is_foreground": isForeground
    ])
  }

  private func emit(_ payload: [String: Any]) {
    DispatchQueue.main.async { [weak self] in
      self?.eventSink?(payload)
    }
  }

  private func handleAudioSessionEvent(_ payload: [String: Any]) {
    if payload["event"] as? String == "audio.interruption",
       payload["phase"] as? String == "began" {
      assistantDonePendingRestart = false
      audioPlayback.stop()
      audioCapture.stop()
      voiceWebSocket.interrupt()
    }
    emit(payload)
  }

  private func handleCaptureEvent(_ payload: [String: Any]) {
    let event = payload["event"] as? String
    if event == "utterance.end" {
      audioCapture.stop()
      voiceWebSocket.endUtterance()
    }
    emit(payload)
  }

  private func handleTransportEvent(_ payload: [String: Any]) {
    let event = payload["event"] as? String
    if event == "assistant.started" || event == "transcript.final" {
      audioCapture.stop()
    }
    if event == "assistant.audio_chunk" {
      enqueueAssistantAudio(payload)
    }
    if event == "assistant.done" {
      assistantDonePendingRestart = true
      restartCaptureAfterPlaybackIfReady()
    }
    if event == "error" {
      assistantDonePendingRestart = false
      audioPlayback.stop()
      audioCapture.stop()
    }
    emit(payload)
  }

  private func enqueueAssistantAudio(_ payload: [String: Any]) {
    guard let audioBase64 = payload["audio_base64"] as? String,
          let data = Data(base64Encoded: audioBase64),
          !data.isEmpty else {
      emit([
        "event": "playback.error",
        "native": true,
        "detail": "Assistant audio chunk was empty or invalid."
      ])
      return
    }

    let contentType = payload["audio_content_type"] as? String ?? "audio/mpeg"
    let text = payload["text"] as? String ?? ""
    audioPlayback.enqueue(RexNativeAudioPlaybackChunk(
      data: data,
      contentType: contentType,
      text: text
    ))
  }

  private func restartCaptureAfterPlaybackIfReady() {
    guard isSessionActive, assistantDonePendingRestart, !audioPlayback.isBusy else {
      return
    }
    assistantDonePendingRestart = false
    do {
      try audioCapture.start()
      emit(["event": "listening", "native": true])
    } catch {
      emit([
        "event": "error",
        "native": true,
        "detail": "Could not restart native microphone capture after playback.",
        "native_error": error.localizedDescription
      ])
    }
  }

  private func restartCaptureAfterInterrupt() {
    guard isSessionActive, !isMuted else {
      return
    }
    do {
      try audioCapture.start()
      emit(["event": "listening", "native": true])
    } catch {
      emit([
        "event": "error",
        "native": true,
        "detail": "Could not restart native microphone capture after interruption.",
        "native_error": error.localizedDescription
      ])
    }
  }
}
