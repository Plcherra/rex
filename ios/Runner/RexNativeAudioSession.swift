import AVFoundation
import Foundation

final class RexNativeAudioSession {
  typealias EventEmitter = ([String: Any]) -> Void

  var onEvent: EventEmitter?

  private let session = AVAudioSession.sharedInstance()
  private var observersRegistered = false
  private var isActive = false

  func activate() throws {
    registerObserversIfNeeded()

    try session.setCategory(
      .playAndRecord,
      mode: .voiceChat,
      options: [.defaultToSpeaker, .allowBluetooth, .allowBluetoothA2DP]
    )
    try session.setPreferredSampleRate(16_000)
    try session.setActive(true)
    isActive = true

    emit([
      "event": "audio.session.activated",
      "native": true,
      "category": session.category.rawValue,
      "mode": session.mode.rawValue,
      "sample_rate": session.sampleRate
    ])
  }

  func deactivate() {
    guard isActive else {
      emit(["event": "audio.session.deactivated", "native": true])
      return
    }

    do {
      try session.setActive(false, options: [.notifyOthersOnDeactivation])
      isActive = false
      emit(["event": "audio.session.deactivated", "native": true])
    } catch {
      emitError("Could not deactivate iOS audio session.", error: error)
    }
  }

  func dispose() {
    deactivate()
    NotificationCenter.default.removeObserver(self)
    observersRegistered = false
  }

  private func registerObserversIfNeeded() {
    guard !observersRegistered else {
      return
    }
    observersRegistered = true

    let center = NotificationCenter.default
    center.addObserver(
      self,
      selector: #selector(handleInterruption(_:)),
      name: AVAudioSession.interruptionNotification,
      object: session
    )
    center.addObserver(
      self,
      selector: #selector(handleRouteChange(_:)),
      name: AVAudioSession.routeChangeNotification,
      object: session
    )
    center.addObserver(
      self,
      selector: #selector(handleMediaServicesWereLost(_:)),
      name: AVAudioSession.mediaServicesWereLostNotification,
      object: session
    )
    center.addObserver(
      self,
      selector: #selector(handleMediaServicesWereReset(_:)),
      name: AVAudioSession.mediaServicesWereResetNotification,
      object: session
    )
  }

  @objc private func handleInterruption(_ notification: Notification) {
    let typeValue = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt
    let type = typeValue.flatMap(AVAudioSession.InterruptionType.init)
    let optionValue = notification.userInfo?[AVAudioSessionInterruptionOptionKey] as? UInt
    let options = AVAudioSession.InterruptionOptions(rawValue: optionValue ?? 0)

    emit([
      "event": "audio.interruption",
      "native": true,
      "phase": type == .began ? "began" : "ended",
      "should_resume": options.contains(.shouldResume)
    ])
  }

  @objc private func handleRouteChange(_ notification: Notification) {
    let reasonValue = notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt
    let reason = reasonValue
      .flatMap(AVAudioSession.RouteChangeReason.init)
      .map(routeChangeReasonName) ?? "unknown"

    emit([
      "event": "audio.route.changed",
      "native": true,
      "reason": reason
    ])
  }

  @objc private func handleMediaServicesWereLost(_ notification: Notification) {
    emit([
      "event": "audio.media_services_lost",
      "native": true,
      "detail": "iOS audio media services were lost."
    ])
  }

  @objc private func handleMediaServicesWereReset(_ notification: Notification) {
    emit([
      "event": "audio.media_services_reset",
      "native": true,
      "detail": "iOS audio media services were reset."
    ])
  }

  private func routeChangeReasonName(
    _ reason: AVAudioSession.RouteChangeReason
  ) -> String {
    switch reason {
    case .newDeviceAvailable:
      return "new_device_available"
    case .oldDeviceUnavailable:
      return "old_device_unavailable"
    case .categoryChange:
      return "category_change"
    case .override:
      return "override"
    case .wakeFromSleep:
      return "wake_from_sleep"
    case .noSuitableRouteForCategory:
      return "no_suitable_route_for_category"
    case .routeConfigurationChange:
      return "route_configuration_change"
    case .unknown:
      return "unknown"
    @unknown default:
      return "unknown"
    }
  }

  private func emit(_ payload: [String: Any]) {
    onEvent?(payload)
  }

  private func emitError(_ detail: String, error: Error) {
    emit([
      "event": "error",
      "native": true,
      "detail": detail,
      "native_error": error.localizedDescription
    ])
  }
}
