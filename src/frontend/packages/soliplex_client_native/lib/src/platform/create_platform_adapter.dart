import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/src/platform/create_platform_adapter_stub.dart'
    if (dart.library.io) 'package:soliplex_client_native/src/platform/create_platform_adapter_io.dart';

/// Creates an HTTP adapter optimized for the current platform.
///
/// Returns:
/// - `CupertinoHttpAdapter` on iOS and macOS (uses NSURLSession)
/// - `DartHttpAdapter` on all other platforms (Android, Windows, Linux, Web)
///
/// The [defaultTimeout] parameter sets the default request timeout.
/// Defaults to 30 seconds.
///
/// Example:
/// ```dart
/// import 'package:soliplex_client_native/soliplex_client_native.dart';
///
/// final adapter = createPlatformAdapter();
/// final response = await adapter.request(
///   'GET',
///   Uri.parse('https://api.example.com'),
/// );
/// adapter.close();
/// ```
HttpClientAdapter createPlatformAdapter({
  Duration defaultTimeout = const Duration(seconds: 30),
}) {
  return createPlatformAdapterImpl(defaultTimeout: defaultTimeout);
}
