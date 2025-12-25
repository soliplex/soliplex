import 'dart:io';

import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/src/clients/cupertino_http_client.dart';

/// Creates platform-specific client for IO platforms.
///
/// Returns [CupertinoHttpClient] on macOS and iOS, otherwise returns
/// [DartHttpClient] for Android, Windows, and Linux.
///
/// Note: Falls back to [DartHttpClient] if native bindings are unavailable
/// (e.g., in Flutter test environment).
SoliplexHttpClient createPlatformClientImpl({
  Duration defaultTimeout = const Duration(seconds: 30),
}) {
  if (Platform.isMacOS || Platform.isIOS) {
    try {
      return CupertinoHttpClient(defaultTimeout: defaultTimeout);
    } catch (e) {
      // Fallback to DartHttpClient if native bindings unavailable
      // (e.g., in Flutter test environment)
      return DartHttpClient(defaultTimeout: defaultTimeout);
    }
  }
  // Fallback to DartHttpClient for Android, Windows, Linux
  return DartHttpClient(defaultTimeout: defaultTimeout);
}
