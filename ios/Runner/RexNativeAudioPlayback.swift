import AVFoundation
import Foundation

struct RexNativeAudioPlaybackChunk {
  let data: Data
  let contentType: String
  let text: String
}

final class RexNativeAudioPlayback: NSObject, AVAudioPlayerDelegate {
  typealias EventEmitter = ([String: Any]) -> Void
  typealias DrainHandler = () -> Void

  var onEvent: EventEmitter?
  var onDrained: DrainHandler?

  private var queue: [RexNativeAudioPlaybackChunk] = []
  private var player: AVAudioPlayer?
  private var isPlaying = false

  var isBusy: Bool {
    isPlaying || !queue.isEmpty
  }

  var isAudioPlaying: Bool {
    isPlaying
  }

  func enqueue(_ chunk: RexNativeAudioPlaybackChunk) {
    guard !chunk.data.isEmpty else {
      return
    }

    guard supports(contentType: chunk.contentType) else {
      emit([
        "event": "playback.error",
        "native": true,
        "detail": "Unsupported native assistant audio format.",
        "audio_content_type": chunk.contentType
      ])
      return
    }

    queue.append(chunk)
    emit([
      "event": "playback.queued",
      "native": true,
      "queue_depth": queue.count,
      "audio_content_type": chunk.contentType,
      "text": chunk.text
    ])
    playNextIfNeeded()
  }

  func stop() {
    queue.removeAll()
    if player != nil || isPlaying {
      player?.stop()
      player = nil
      isPlaying = false
      emit(["event": "speaking.ended", "native": true, "reason": "stopped"])
    }
  }

  private func playNextIfNeeded() {
    guard !isPlaying, !queue.isEmpty else {
      return
    }

    let chunk = queue.removeFirst()
    do {
      let player = try AVAudioPlayer(data: chunk.data)
      player.delegate = self
      player.prepareToPlay()
      self.player = player
      isPlaying = true
      emit([
        "event": "speaking.started",
        "native": true,
        "queue_depth": queue.count,
        "audio_content_type": chunk.contentType,
        "text": chunk.text
      ])
      if !player.play() {
        finishCurrentPlayback(
          success: false,
          detail: "Native assistant audio did not start playing."
        )
      }
    } catch {
      emit([
        "event": "playback.error",
        "native": true,
        "detail": "Could not play native assistant audio.",
        "native_error": error.localizedDescription
      ])
      playNextIfNeeded()
    }
  }

  func audioPlayerDidFinishPlaying(
    _ player: AVAudioPlayer,
    successfully flag: Bool
  ) {
    finishCurrentPlayback(success: flag, detail: nil)
  }

  func audioPlayerDecodeErrorDidOccur(
    _ player: AVAudioPlayer,
    error: Error?
  ) {
    finishCurrentPlayback(
      success: false,
      detail: error?.localizedDescription ?? "Native assistant audio decode failed."
    )
  }

  private func finishCurrentPlayback(success: Bool, detail: String?) {
    player = nil
    isPlaying = false

    if !success {
      emit([
        "event": "playback.error",
        "native": true,
        "detail": detail ?? "Native assistant audio playback failed."
      ])
    }

    if queue.isEmpty {
      emit([
        "event": "speaking.ended",
        "native": true,
        "reason": success ? "drained" : "failed"
      ])
      onDrained?()
    } else {
      playNextIfNeeded()
    }
  }

  private func supports(contentType: String) -> Bool {
    let normalized = contentType.lowercased()
    return normalized == "audio/mpeg" ||
      normalized == "audio/mp3" ||
      normalized == "audio/x-mpeg" ||
      normalized == "audio/mpeg3"
  }

  private func emit(_ payload: [String: Any]) {
    onEvent?(payload)
  }
}
