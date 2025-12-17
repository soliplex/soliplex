/// Application configuration for AM1.
///
/// In AM7, this will be loaded from settings storage.
class AppConfig {
  const AppConfig({
    required this.baseUrl,
    required this.appName,
    required this.version,
  });

  /// Default configuration for AM1.
  factory AppConfig.defaults() {
    return const AppConfig(
      baseUrl: 'http://localhost:8000',
      appName: 'Soliplex',
      version: '1.0.0-dev',
    );
  }

  final String baseUrl;
  final String appName;
  final String version;

  AppConfig copyWith({
    String? baseUrl,
    String? appName,
    String? version,
  }) {
    return AppConfig(
      baseUrl: baseUrl ?? this.baseUrl,
      appName: appName ?? this.appName,
      version: version ?? this.version,
    );
  }
}
