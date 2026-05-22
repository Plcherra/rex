import AVFoundation
import Foundation

enum RexPCMConverterError: Error {
  case unsupportedInputFormat
  case converterUnavailable
  case conversionFailed(String)
  case outputBufferUnavailable
}

final class RexPCMConverter {
  private let outputSampleRate: Double
  private let outputChannelCount: AVAudioChannelCount
  private var converter: AVAudioConverter?
  private var inputFormat: AVAudioFormat?

  init(
    outputSampleRate: Double = 16_000,
    outputChannelCount: AVAudioChannelCount = 1
  ) {
    self.outputSampleRate = outputSampleRate
    self.outputChannelCount = outputChannelCount
  }

  func convert(_ inputBuffer: AVAudioPCMBuffer) throws -> Data {
    let sourceFormat = inputBuffer.format
    guard sourceFormat.channelCount > 0, sourceFormat.sampleRate > 0 else {
      throw RexPCMConverterError.unsupportedInputFormat
    }

    let converter = try converterFor(inputFormat: sourceFormat)
    guard let outputFormat = AVAudioFormat(
      commonFormat: .pcmFormatInt16,
      sampleRate: outputSampleRate,
      channels: outputChannelCount,
      interleaved: false
    ) else {
      throw RexPCMConverterError.outputBufferUnavailable
    }

    let ratio = outputSampleRate / sourceFormat.sampleRate
    let outputCapacity = AVAudioFrameCount(
      max(1, ceil(Double(inputBuffer.frameLength) * ratio) + 256)
    )
    guard let outputBuffer = AVAudioPCMBuffer(
      pcmFormat: outputFormat,
      frameCapacity: outputCapacity
    ) else {
      throw RexPCMConverterError.outputBufferUnavailable
    }

    var didProvideInput = false
    var conversionError: NSError?
    let status = converter.convert(
      to: outputBuffer,
      error: &conversionError
    ) { _, outStatus in
      if didProvideInput {
        outStatus.pointee = .noDataNow
        return nil
      }
      didProvideInput = true
      outStatus.pointee = .haveData
      return inputBuffer
    }

    if let conversionError {
      throw RexPCMConverterError.conversionFailed(conversionError.localizedDescription)
    }
    switch status {
    case .haveData, .inputRanDry, .endOfStream:
      return pcm16Data(from: outputBuffer)
    case .error:
      throw RexPCMConverterError.conversionFailed("AVAudioConverter returned an error.")
    @unknown default:
      throw RexPCMConverterError.conversionFailed("AVAudioConverter returned an unknown status.")
    }
  }

  private func converterFor(inputFormat: AVAudioFormat) throws -> AVAudioConverter {
    if let converter,
       let cachedInputFormat = self.inputFormat,
       formatsMatch(cachedInputFormat, inputFormat) {
      return converter
    }

    guard let outputFormat = AVAudioFormat(
      commonFormat: .pcmFormatInt16,
      sampleRate: outputSampleRate,
      channels: outputChannelCount,
      interleaved: false
    ) else {
      throw RexPCMConverterError.outputBufferUnavailable
    }
    guard let converter = AVAudioConverter(from: inputFormat, to: outputFormat) else {
      throw RexPCMConverterError.converterUnavailable
    }
    self.inputFormat = inputFormat
    self.converter = converter
    return converter
  }

  private func formatsMatch(_ lhs: AVAudioFormat, _ rhs: AVAudioFormat) -> Bool {
    lhs.sampleRate == rhs.sampleRate &&
      lhs.channelCount == rhs.channelCount &&
      lhs.commonFormat == rhs.commonFormat &&
      lhs.isInterleaved == rhs.isInterleaved
  }

  private func pcm16Data(from buffer: AVAudioPCMBuffer) -> Data {
    guard let channel = buffer.int16ChannelData?[0], buffer.frameLength > 0 else {
      return Data()
    }
    let byteCount = Int(buffer.frameLength) * MemoryLayout<Int16>.size
    return Data(bytes: channel, count: byteCount)
  }
}
