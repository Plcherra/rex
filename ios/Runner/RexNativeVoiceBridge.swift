import Flutter
import Foundation

private enum RexNativeVoiceState: String {
  case idle
  case listening
  case userSpeaking = "user_speaking"
  case waitingForAssistant = "waiting_for_assistant"
  case assistantSpeaking = "assistant_speaking"
  case restartingListening = "restarting_listening"
  case failed
}

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
  private var nativeState = RexNativeVoiceState.idle
  private var firstAssistantAudioChunkSeen = false
  private var currentConfig: RexNativeVoiceWebSocketConfig?

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
      guard let self else {
        return
      }
      do {
        try self.ensureTransportConnected()
        self.voiceWebSocket.sendAudioChunk(data)
        self.emit([
          "event": "audio.chunk",
          "native": true,
          "byte_count": data.count
        ])
      } catch {
        self.emit([
          "event": "error",
          "native": true,
          "detail": "Could not reopen native voice stream for microphone audio.",
          "native_error": error.localizedDescription
        ])
      }
    }
    audioPlayback.onEvent = { [weak self] payload in
      self?.handlePlaybackEvent(payload)
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
    currentConfig = config
    assistantDonePendingRestart = false
    firstAssistantAudioChunkSeen = false
    try audioSession.activate()
    do {
      try voiceWebSocket.start(config: config)
      try audioCapture.start()
    } catch {
      voiceWebSocket.stop(sendSessionEnd: false)
      audioSession.deactivate()
      currentConfig = nil
      throw error
    }
    isSessionActive = true
    transition(to: .listening, reason: "session_started")
    emit(["event": "listening", "native": true])
  }

  private func stopSession() {
    guard isSessionActive else {
      assistantDonePendingRestart = false
      audioPlayback.stop()
      audioCapture.stop()
      voiceWebSocket.stop()
      audioSession.deactivate()
      currentConfig = nil
      transition(to: .idle, reason: "session_stopped")
      emit(["event": "session.ended", "native": true])
      return
    }
    isSessionActive = false
    assistantDonePendingRestart = false
    audioPlayback.stop()
    audioCapture.stop()
    voiceWebSocket.stop()
    audioSession.deactivate()
    currentConfig = nil
    transition(to: .idle, reason: "session_stopped")
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
    transition(to: .restartingListening, reason: "user_interrupt")
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
    emitBackgroundAudioGapIfNeeded(reason: "foreground_changed")
  }

  private func emit(_ payload: [String: Any]) {
    var enriched = payload
    enriched["native_state"] = nativeState.rawValue
    enriched["is_foreground"] = isForeground
    enriched["is_capturing"] = audioCapture.isActive
    enriched["is_playing"] = audioPlayback.isAudioPlaying
    enriched["audio_session_active"] = audioSession.isAudioSessionActive
    enriched["websocket_connected"] = voiceWebSocket.isConnected
    enriched["timestamp_ms"] = Int64(Date().timeIntervalSince1970 * 1000)
    logTelemetryIfUseful(enriched)
    DispatchQueue.main.async { [weak self] in
      self?.eventSink?(enriched)
    }
  }

  private func logTelemetryIfUseful(_ payload: [String: Any]) {
    guard let event = payload["event"] as? String else {
      return
    }
    let loggedEvents: Set<String> = [
      "foreground.changed",
      "utterance.end",
      "transport.closed",
      "assistant.started",
      "assistant.audio_chunk",
      "assistant.done",
      "speaking.started",
      "speaking.ended",
      "error",
      "playback.error",
      "capture.error"
    ]
    guard event.hasPrefix("native.turn.") || loggedEvents.contains(event) else {
      return
    }
    NSLog(
      "RexNativeVoice event=%@ state=%@ foreground=%@ capturing=%@ playing=%@ websocket=%@ audio_session=%@ reason=%@ detail=%@",
      event,
      String(describing: payload["native_state"] ?? ""),
      String(describing: payload["is_foreground"] ?? ""),
      String(describing: payload["is_capturing"] ?? ""),
      String(describing: payload["is_playing"] ?? ""),
      String(describing: payload["websocket_connected"] ?? ""),
      String(describing: payload["audio_session_active"] ?? ""),
      String(describing: payload["reason"] ?? ""),
      String(describing: payload["detail"] ?? "")
    )
  }

  private func transition(to nextState: RexNativeVoiceState, reason: String) {
    nativeState = nextState
    emitTimelineEvent(transitionEventName(for: nextState), reason: reason)
  }

  private func transitionEventName(for state: RexNativeVoiceState) -> String {
    switch state {
    case .idle:
      return "native.turn.idle"
    case .listening:
      return "native.turn.listening"
    case .userSpeaking:
      return "native.turn.user_speaking"
    case .waitingForAssistant:
      return "native.turn.waiting_for_assistant"
    case .assistantSpeaking:
      return "native.turn.playback_started"
    case .restartingListening:
      return "native.turn.capture_restarting"
    case .failed:
      return "native.turn.failed"
    }
  }

  private func emitTimelineEvent(
    _ event: String,
    reason: String,
    extra: [String: Any] = [:]
  ) {
    var payload = extra
    payload["event"] = event
    payload["native"] = true
    payload["reason"] = reason
    emit(payload)
  }

  private func emitBackgroundAudioGapIfNeeded(reason: String) {
    guard nativeState == .waitingForAssistant,
          !isForeground,
          !audioCapture.isActive,
          !audioPlayback.isAudioPlaying else {
      return
    }
    emitTimelineEvent(
      "native.turn.background_audio_gap",
      reason: reason,
      extra: [
        "detail": "Native voice is waiting for assistant audio in the background while capture and playback are both inactive."
      ]
    )
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
    if event == "speech.started" {
      transition(to: .userSpeaking, reason: "speech_started")
    }
    if event == "utterance.end" {
      let reason = payload["reason"] as? String ?? "utterance_end"
      firstAssistantAudioChunkSeen = false
      transition(to: .waitingForAssistant, reason: reason)
      audioCapture.stop()
      emitBackgroundAudioGapIfNeeded(reason: "utterance_end_after_capture_stop")
      do {
        try ensureTransportConnected()
        voiceWebSocket.endUtterance()
      } catch {
        emit([
          "event": "error",
          "native": true,
          "detail": "Could not send native voice turn to Rex.",
          "native_error": error.localizedDescription
        ])
        transition(to: .failed, reason: "utterance_end_send_failed")
      }
    }
    emit(payload)
  }

  private func handleTransportEvent(_ payload: [String: Any]) {
    let event = payload["event"] as? String
    if event == "assistant.started" {
      emitTimelineEvent("native.turn.assistant_started", reason: "assistant_started")
      audioCapture.stop()
    }
    if event == "assistant.audio_chunk" {
      if !firstAssistantAudioChunkSeen {
        firstAssistantAudioChunkSeen = true
        emitTimelineEvent("native.turn.first_audio_chunk", reason: "assistant_audio_chunk")
      }
      enqueueAssistantAudio(payload)
    }
    if event == "assistant.done" {
      assistantDonePendingRestart = true
      restartCaptureAfterPlaybackIfReady()
    }
    if event == "transport.closed",
       payload["reason"] as? String == "turn_complete",
       isSessionActive {
      reconnectTransportForNextTurn()
    }
    if event == "error" {
      assistantDonePendingRestart = false
      audioPlayback.stop()
      audioCapture.stop()
      transition(to: .failed, reason: "transport_error")
    }
    emit(payload)
  }

  private func handlePlaybackEvent(_ payload: [String: Any]) {
    let event = payload["event"] as? String
    if event == "speaking.started" {
      transition(to: .assistantSpeaking, reason: "speaking_started")
    }
    if event == "speaking.ended",
       assistantDonePendingRestart {
      transition(to: .restartingListening, reason: "speaking_ended")
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
      transition(to: .restartingListening, reason: "assistant_done")
      try ensureTransportConnected()
      try audioCapture.start()
      firstAssistantAudioChunkSeen = false
      transition(to: .listening, reason: "capture_restarted")
      emitTimelineEvent("native.turn.capture_restarted", reason: "assistant_done")
      emit(["event": "listening", "native": true])
    } catch {
      emit([
        "event": "error",
        "native": true,
        "detail": "Could not restart native microphone capture after playback.",
        "native_error": error.localizedDescription
      ])
      transition(to: .failed, reason: "capture_restart_failed")
    }
  }

  private func restartCaptureAfterInterrupt() {
    guard isSessionActive, !isMuted else {
      return
    }
    do {
      transition(to: .restartingListening, reason: "interrupt")
      try ensureTransportConnected()
      try audioCapture.start()
      firstAssistantAudioChunkSeen = false
      transition(to: .listening, reason: "interrupt_restarted_capture")
      emitTimelineEvent("native.turn.capture_restarted", reason: "interrupt")
      emit(["event": "listening", "native": true])
    } catch {
      emit([
        "event": "error",
        "native": true,
        "detail": "Could not restart native microphone capture after interruption.",
        "native_error": error.localizedDescription
      ])
      transition(to: .failed, reason: "interrupt_capture_restart_failed")
    }
  }

  private func ensureTransportConnected() throws {
    guard !voiceWebSocket.isConnected else {
      return
    }
    guard let currentConfig else {
      return
    }
    try voiceWebSocket.start(config: currentConfig)
  }

  private func reconnectTransportForNextTurn() {
    guard isSessionActive else {
      return
    }
    do {
      try ensureTransportConnected()
    } catch {
      emit([
        "event": "error",
        "native": true,
        "detail": "Could not prepare native voice stream for the next turn.",
        "native_error": error.localizedDescription
      ])
    }
  }
}
