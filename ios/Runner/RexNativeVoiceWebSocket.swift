import Foundation

enum RexNativeVoiceWebSocketError: Error {
  case invalidBackendURL
  case invalidStreamURL
}

struct RexNativeVoiceWebSocketConfig {
  let backendBaseURL: String
  let conversationID: String?
  let sampleRate: Int
  let inputMimeType: String
}

final class RexNativeVoiceWebSocket {
  typealias EventEmitter = ([String: Any]) -> Void

  var onEvent: EventEmitter?
  var isConnected: Bool {
    if DispatchQueue.getSpecific(key: Self.queueKey) == true {
      return isActive && task != nil
    }
    return queue.sync {
      isActive && task != nil
    }
  }

  private static let queueKey = DispatchSpecificKey<Bool>()
  private let queue = DispatchQueue(label: "rex.native.voice.websocket")
  private let urlSession = URLSession(configuration: .default)
  private var task: URLSessionWebSocketTask?
  private var isActive = false
  private var assistantTurnCompleted = false
  private var normalCloseExpected = false
  private var connectTimeout: DispatchWorkItem?
  private var assistantTimeout: DispatchWorkItem?

  init() {
    queue.setSpecific(key: Self.queueKey, value: true)
  }

  func start(config: RexNativeVoiceWebSocketConfig) throws {
    let streamURL = try makeStreamURL(from: config.backendBaseURL)
    let webSocketTask = urlSession.webSocketTask(with: streamURL)
    if DispatchQueue.getSpecific(key: Self.queueKey) == true {
      startOnQueue(task: webSocketTask, streamURL: streamURL, config: config)
    } else {
      queue.sync {
        startOnQueue(task: webSocketTask, streamURL: streamURL, config: config)
      }
    }
  }

  func sendAudioChunk(_ data: Data) {
    guard !data.isEmpty else {
      return
    }
    queue.async { [weak self] in
      guard let self, self.isActive, let task = self.task else {
        return
      }
      task.send(.data(data)) { [weak self] error in
        if let error {
          self?.emitError(
            "Could not stream native voice audio.",
            code: "native_audio_send_failed",
            error: error
          )
        }
      }
    }
  }

  func endUtterance() {
    sendJSON(["event": "utterance.end"])
    emit(["event": "transport.utterance_end_sent", "native": true])
    armAssistantTimeout()
  }

  func interrupt() {
    cancelAssistantTimeout()
    sendJSON(["event": "user.interrupt"])
  }

  func stop(sendSessionEnd: Bool = true) {
    queue.async { [weak self] in
      guard let self else {
        return
      }
      self.stopOnQueue(sendSessionEnd: sendSessionEnd, emitClosed: true)
    }
  }

  private func stopOnQueue(sendSessionEnd: Bool, emitClosed: Bool) {
    cancelConnectTimeout()
    cancelAssistantTimeout()
    normalCloseExpected = true
    if sendSessionEnd, isActive {
      sendJSONOnQueue(["event": "session.end"])
    }
    let hadTask = task != nil || isActive
    isActive = false
    assistantTurnCompleted = false
    task?.cancel(with: .normalClosure, reason: nil)
    task = nil
    if emitClosed, hadTask {
      emit(["event": "transport.closed", "native": true])
    }
  }

  private func startOnQueue(
    task webSocketTask: URLSessionWebSocketTask,
    streamURL: URL,
    config: RexNativeVoiceWebSocketConfig
  ) {
    stopOnQueue(sendSessionEnd: false, emitClosed: false)
    task = webSocketTask
    isActive = true
    assistantTurnCompleted = false
    normalCloseExpected = false

    emit([
      "event": "transport.connecting",
      "native": true,
      "url": streamURL.absoluteString
    ])

    webSocketTask.resume()
    armConnectTimeout()
    receiveNext()
    sendSessionStart(config)
  }

  private func sendSessionStart(_ config: RexNativeVoiceWebSocketConfig) {
    var payload: [String: Any] = [
      "event": "session.start",
      "input_mime_type": config.inputMimeType,
      "sample_rate": config.sampleRate,
      "client": "ios_native"
    ]
    if let conversationID = config.conversationID, !conversationID.isEmpty {
      payload["conversation_id"] = conversationID
    }
    sendJSON(payload)
  }

  private func sendJSON(_ payload: [String: Any]) {
    queue.async { [weak self] in
      self?.sendJSONOnQueue(payload)
    }
  }

  private func sendJSONOnQueue(_ payload: [String: Any]) {
    guard isActive, let task else {
      return
    }
    do {
      let data = try JSONSerialization.data(withJSONObject: payload)
      guard let text = String(data: data, encoding: .utf8) else {
        return
      }
      task.send(.string(text)) { [weak self] error in
        if let error {
          self?.emitError(
            "Could not send native voice event.",
            code: "native_event_send_failed",
            error: error
          )
        }
      }
    } catch {
      emitError(
        "Could not encode native voice event.",
        code: "native_event_encode_failed",
        error: error
      )
    }
  }

  private func receiveNext() {
    queue.async { [weak self] in
      guard let self, self.isActive, let task = self.task else {
        return
      }
      task.receive { [weak self] result in
        guard let self else {
          return
        }
        self.queue.async {
          guard self.isActive, self.task === task else {
            return
          }

          switch result {
          case let .success(message):
            self.handle(message)
            self.receiveNext()
          case let .failure(error):
            if self.assistantTurnCompleted || self.normalCloseExpected {
              self.handleGracefulClose(reason: self.assistantTurnCompleted ? "turn_complete" : "client_stop")
            } else if self.isActive {
              self.emitError(
                "Native voice stream closed unexpectedly.",
                code: "native_stream_closed",
                error: error
              )
              self.isActive = false
              self.task = nil
            }
          }
        }
      }
    }
  }

  private func handle(_ message: URLSessionWebSocketTask.Message) {
    switch message {
    case let .string(text):
      handleServerText(text)
    case let .data(data):
      emit([
        "event": "transport.binary_received",
        "native": true,
        "byte_count": data.count
      ])
    @unknown default:
      emitError(
        "Native voice stream returned an unknown message type.",
        code: "native_stream_unknown_message"
      )
    }
  }

  private func handleServerText(_ text: String) {
    guard let data = text.data(using: .utf8) else {
      emitError("Native voice stream returned unreadable text.", code: "native_stream_bad_text")
      return
    }

    do {
      guard var payload = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        emitError("Native voice stream returned invalid JSON.", code: "native_stream_bad_json")
        return
      }

      let event = payload["event"] as? String ?? "unknown"
      payload["native"] = true
      payload["transport"] = "ios_native"

      if event == "session.started" {
        cancelConnectTimeout()
      }
      if event == "assistant.started" || event == "assistant.token" || event == "assistant.audio_chunk" {
        cancelAssistantTimeout()
      }
      if event == "assistant.done" || event == "session.ended" || event == "error" {
        cancelAssistantTimeout()
      }
      if event == "assistant.done" || event == "session.ended" {
        assistantTurnCompleted = true
      }

      emit(payload)
    } catch {
      emitError(
        "Native voice stream returned invalid JSON.",
        code: "native_stream_bad_json",
        error: error
      )
    }
  }

  private func makeStreamURL(from backendBaseURL: String) throws -> URL {
    guard var components = URLComponents(string: backendBaseURL) else {
      throw RexNativeVoiceWebSocketError.invalidBackendURL
    }

    switch components.scheme {
    case "https":
      components.scheme = "wss"
    case "http":
      components.scheme = "ws"
    case "wss", "ws":
      break
    default:
      throw RexNativeVoiceWebSocketError.invalidBackendURL
    }

    let trimmedPath = components.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    components.path = trimmedPath.isEmpty
      ? "/voice/stream"
      : "/\(trimmedPath)/voice/stream"

    guard let url = components.url else {
      throw RexNativeVoiceWebSocketError.invalidStreamURL
    }
    return url
  }

  private func armConnectTimeout() {
    cancelConnectTimeout()
    let workItem = DispatchWorkItem { [weak self] in
      self?.emitError(
        "Native voice stream did not confirm the session in time.",
        code: "native_connect_timeout"
      )
    }
    connectTimeout = workItem
    queue.asyncAfter(deadline: .now() + 10, execute: workItem)
  }

  private func cancelConnectTimeout() {
    connectTimeout?.cancel()
    connectTimeout = nil
  }

  private func armAssistantTimeout() {
    cancelAssistantTimeout()
    let workItem = DispatchWorkItem { [weak self] in
      self?.emitError(
        "Rex did not start answering the native voice turn in time.",
        code: "native_assistant_timeout"
      )
    }
    assistantTimeout = workItem
    queue.asyncAfter(deadline: .now() + 25, execute: workItem)
  }

  private func cancelAssistantTimeout() {
    assistantTimeout?.cancel()
    assistantTimeout = nil
  }

  private func handleGracefulClose(reason: String) {
    cancelConnectTimeout()
    cancelAssistantTimeout()
    isActive = false
    task = nil
    assistantTurnCompleted = false
    normalCloseExpected = false
    emit([
      "event": "transport.closed",
      "native": true,
      "reason": reason
    ])
  }

  private func emit(_ payload: [String: Any]) {
    onEvent?(payload)
  }

  private func emitError(
    _ detail: String,
    code: String,
    error: Error? = nil
  ) {
    var payload: [String: Any] = [
      "event": "error",
      "native": true,
      "code": code,
      "detail": detail
    ]
    if let error {
      payload["native_error"] = error.localizedDescription
    }
    emit(payload)
  }
}
