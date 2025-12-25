import 'package:soliplex_client/soliplex_client.dart';

/// Fallback implementation for non-IO platforms (Web).
///
/// Returns [DartHttpAdapter] as the default adapter for web platform.
SoliplexHttpClient createPlatformAdapterImpl({
  Duration defaultTimeout = const Duration(seconds: 30),
}) {
  // Web platform uses DartHttpAdapter
  return DartHttpAdapter(defaultTimeout: defaultTimeout);
}
