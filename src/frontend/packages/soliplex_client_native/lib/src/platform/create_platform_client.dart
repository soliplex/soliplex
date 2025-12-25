import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/src/platform/create_platform_client_stub.dart'
    if (dart.library.io) 'package:soliplex_client_native/src/platform/create_platform_client_io.dart';

/// Creates an HTTP client optimized for the current platform.
///
/// Returns:
/// - `CupertinoHttpClient` on iOS and macOS (uses NSURLSession)
/// - `DartHttpClient` on all other platforms (Android, Windows, Linux, Web)
///
/// The [defaultTimeout] parameter sets the default request timeout.
/// Defaults to 30 seconds.
///
/// Example:
/// ```dart
/// import 'package:soliplex_client_native/soliplex_client_native.dart';
///
/// final client = createPlatformClient();
/// final response = await client.request(
///   'GET',
///   Uri.parse('https://api.example.com'),
/// );
/// client.close();
/// ```
SoliplexHttpClient createPlatformClient({
  Duration defaultTimeout = const Duration(seconds: 30),
}) {
  return createPlatformClientImpl(defaultTimeout: defaultTimeout);
}
