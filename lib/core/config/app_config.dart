abstract final class AppConfig {
  static const String backendBaseUrl = String.fromEnvironment(
    'REX_BACKEND_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const bool cloudVoiceEnabled = bool.fromEnvironment(
    'REX_CLOUD_VOICE_ENABLED',
    defaultValue: true,
  );
}
