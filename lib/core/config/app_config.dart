abstract final class AppConfig {
  static const String backendBaseUrl = String.fromEnvironment(
    'REX_BACKEND_URL',
    defaultValue: 'http://localhost:8000',
  );
}
