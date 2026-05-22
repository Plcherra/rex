import AVFoundation
import Foundation

final class RexNativeAudioCapture {
  typealias EventEmitter = ([String: Any]) -> Void
  typealias AudioChunkHandler = (Data) -> Void

  var onEvent: EventEmitter?
  var onAudioChunk: AudioChunkHandler?

  private let queue = DispatchQueue(label: "rex.native.audio.capture")
  private let converter = RexPCMConverter()
  private var engine: AVAudioEngine?
  private var isCapturing = false
  private var isMuted = false

  private var captureStartedAt: Date?
  private var speechStartedAt: Date?
  private var lastSpeechAt: Date?
  private var hasSpeech = false
  private var speechStartedEmitted = false
  private var speechEndedEmitted = false
  private var noSpeechTimeoutEmitted = false

  private let speechStartThresholdDb = -52.0
  private let silenceThresholdDb = -68.0
  private let minimumSpeechDuration: TimeInterval = 0.20
  private let silenceAfterSpeech: TimeInterval = 10.00
  private let noSpeechStatusInterval: TimeInterval = 30.00
  private let maxUtteranceDuration: TimeInterval = 180.00

  func start() throws {
    stop()
    resetEndpointState()

    let engine = AVAudioEngine()
    let inputNode = engine.inputNode
    let inputFormat = inputNode.outputFormat(forBus: 0)

    inputNode.installTap(
      onBus: 0,
      bufferSize: 1024,
      format: inputFormat
    ) { [weak self] buffer, _ in
      self?.queue.async {
        self?.handle(buffer)
      }
    }

    engine.prepare()
    try engine.start()
    self.engine = engine
    isCapturing = true
    emit([
      "event": "capture.started",
      "native": true,
      "input_sample_rate": inputFormat.sampleRate,
      "input_channels": inputFormat.channelCount
    ])
  }

  func stop() {
    guard isCapturing || engine != nil else {
      return
    }
    engine?.inputNode.removeTap(onBus: 0)
    engine?.stop()
    engine = nil
    isCapturing = false
    emit(["event": "capture.stopped", "native": true])
    resetEndpointState()
  }

  func setMuted(_ isMuted: Bool) {
    self.isMuted = isMuted
    emit(["event": "capture.muted.changed", "native": true, "is_muted": isMuted])
  }

  private func handle(_ buffer: AVAudioPCMBuffer) {
    guard isCapturing else {
      return
    }

    let pcmData: Data
    do {
      pcmData = try converter.convert(buffer)
    } catch {
      emit([
        "event": "capture.error",
        "native": true,
        "detail": "Could not convert native microphone audio to PCM16.",
        "native_error": error.localizedDescription
      ])
      return
    }

    guard !pcmData.isEmpty else {
      return
    }

    guard !isMuted else {
      return
    }

    onAudioChunk?(pcmData)

    let now = Date()
    let decibels = pcm16Decibels(pcmData)
    updateEndpointing(currentDb: decibels, now: now)
    emit([
      "event": "audio.captured",
      "native": true,
      "byte_count": pcmData.count,
      "decibels": decibels
    ])
  }

  private func updateEndpointing(currentDb: Double, now: Date) {
    if captureStartedAt == nil {
      captureStartedAt = now
    }
    guard let captureStartedAt else {
      return
    }

    let elapsed = now.timeIntervalSince(captureStartedAt)
    if !hasSpeech, elapsed >= noSpeechStatusInterval, !noSpeechTimeoutEmitted {
      noSpeechTimeoutEmitted = true
      emit([
        "event": "capture.idle_timeout",
        "native": true,
        "detail": "Native microphone is still listening, but no speech has been detected yet."
      ])
    }

    if hasSpeech,
       let speechStartedAt,
       now.timeIntervalSince(speechStartedAt) >= maxUtteranceDuration,
       !speechEndedEmitted {
      emitSpeechEnded(reason: "max_duration")
      return
    }

    if currentDb >= speechStartThresholdDb {
      if speechStartedAt == nil {
        speechStartedAt = now
      }
      noSpeechTimeoutEmitted = false
      lastSpeechAt = now
      if let speechStartedAt,
         now.timeIntervalSince(speechStartedAt) >= minimumSpeechDuration,
         !speechStartedEmitted {
        hasSpeech = true
        speechStartedEmitted = true
        emit(["event": "speech.started", "native": true])
      }
      return
    }

    if currentDb > silenceThresholdDb {
      lastSpeechAt = now
      return
    }

    if !hasSpeech {
      speechStartedAt = nil
      return
    }

    if let lastSpeechAt,
       now.timeIntervalSince(lastSpeechAt) >= silenceAfterSpeech,
       !speechEndedEmitted {
      emitSpeechEnded(reason: "silence")
    }
  }

  private func emitSpeechEnded(reason: String) {
    speechEndedEmitted = true
    emit([
      "event": "speech.ended",
      "native": true,
      "reason": reason
    ])
    emit([
      "event": "utterance.end",
      "native": true,
      "reason": reason
    ])
  }

  private func resetEndpointState() {
    captureStartedAt = nil
    speechStartedAt = nil
    lastSpeechAt = nil
    hasSpeech = false
    speechStartedEmitted = false
    speechEndedEmitted = false
    noSpeechTimeoutEmitted = false
  }

  private func pcm16Decibels(_ data: Data) -> Double {
    guard data.count >= MemoryLayout<Int16>.size else {
      return -160
    }

    var sumSquares = 0.0
    var sampleCount = 0
    data.withUnsafeBytes { rawBuffer in
      guard let base = rawBuffer.bindMemory(to: Int16.self).baseAddress else {
        return
      }
      for index in 0 ..< data.count / MemoryLayout<Int16>.size {
        let sample = Double(Int16(littleEndian: base[index])) / 32_768.0
        sumSquares += sample * sample
        sampleCount += 1
      }
    }

    guard sampleCount > 0, sumSquares > 0 else {
      return -160
    }
    let rms = sqrt(sumSquares / Double(sampleCount))
    return 20 * log10(rms)
  }

  private func emit(_ payload: [String: Any]) {
    onEvent?(payload)
  }
}
