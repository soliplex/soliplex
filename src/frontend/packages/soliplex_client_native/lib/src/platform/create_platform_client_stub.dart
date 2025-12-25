import 'package:soliplex_client/soliplex_client.dart';

/// Fallback implementation for non-IO platforms (Web).
///
/// Returns [DartHttpClient] as the default client for web platform.
SoliplexHttpClient createPlatformClientImpl({
  Duration defaultTimeout = const Duration(seconds: 30),
}) {
  // Web platform uses DartHttpClient
  return DartHttpClient(defaultTimeout: defaultTimeout);
}
