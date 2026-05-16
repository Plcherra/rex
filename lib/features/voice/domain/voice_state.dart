enum VoicePhase {
  idle,
  recording,
  uploading,
  listening,
  transcribing,
  thinking,
  generatingSpeech,
  speaking,
  failed,
  permissionDenied,
}

class VoiceState {
  const VoiceState({
    this.phase = VoicePhase.idle,
    this.partialTranscript = '',
    this.finalTranscript = '',
    this.spokenResponseText = '',
    this.errorMessage,
  });

  final VoicePhase phase;
  final String partialTranscript;
  final String finalTranscript;
  final String spokenResponseText;
  final String? errorMessage;

  bool get isIdle => phase == VoicePhase.idle;

  bool get isBusy {
    return switch (phase) {
      VoicePhase.recording ||
      VoicePhase.uploading ||
      VoicePhase.listening ||
      VoicePhase.transcribing ||
      VoicePhase.thinking ||
      VoicePhase.generatingSpeech ||
      VoicePhase.speaking => true,
      VoicePhase.idle ||
      VoicePhase.failed ||
      VoicePhase.permissionDenied => false,
    };
  }

  bool get canStartListening {
    return phase == VoicePhase.idle ||
        phase == VoicePhase.failed ||
        phase == VoicePhase.permissionDenied;
  }

  VoiceState copyWith({
    VoicePhase? phase,
    String? partialTranscript,
    String? finalTranscript,
    String? spokenResponseText,
    String? errorMessage,
    bool clearPartialTranscript = false,
    bool clearFinalTranscript = false,
    bool clearSpokenResponseText = false,
    bool clearError = false,
  }) {
    return VoiceState(
      phase: phase ?? this.phase,
      partialTranscript: clearPartialTranscript
          ? ''
          : partialTranscript ?? this.partialTranscript,
      finalTranscript: clearFinalTranscript
          ? ''
          : finalTranscript ?? this.finalTranscript,
      spokenResponseText: clearSpokenResponseText
          ? ''
          : spokenResponseText ?? this.spokenResponseText,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}
