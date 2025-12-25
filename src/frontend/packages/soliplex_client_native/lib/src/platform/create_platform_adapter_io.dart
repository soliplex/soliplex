import 'dart:io';

import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/src/adapters/cupertino_http_adapter.dart';

/// Creates platform-specific adapter for IO platforms.
///
/// Returns [CupertinoHttpAdapter] on macOS and iOS, otherwise returns
/// [DartHttpClient] for Android, Windows, and Linux.
///
/// Note: Falls back to [DartHttpClient] if native bindings are unavailable
/// (e.g., in Flutter test environment).
SoliplexHttpClient createPlatformAdapterImpl({
  Duration defaultTimeout = const Duration(seconds: 30),
}) {
  if (Platform.isMacOS || Platform.isIOS) {
    try {
      return CupertinoHttpAdapter(defaultTimeout: defaultTimeout);
    } catch (e) {
      // Fallback to DartHttpClient if native bindings unavailable
      // (e.g., in Flutter test environment)
      return DartHttpClient(defaultTimeout: defaultTimeout);
    }
  }
  // Fallback to DartHttpClient for Android, Windows, Linux
  return DartHttpClient(defaultTimeout: defaultTimeout);
}
