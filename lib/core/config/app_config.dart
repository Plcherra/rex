abstract final class AppConfig {
  static const String backendBaseUrl = String.fromEnvironment(
    'REX_BACKEND_URL',
    defaultValue: 'https://api.rexpilot.com',
  );

  static const bool cloudVoiceEnabled = bool.fromEnvironment(
    'REX_CLOUD_VOICE_ENABLED',
    defaultValue: true,
  );
}
