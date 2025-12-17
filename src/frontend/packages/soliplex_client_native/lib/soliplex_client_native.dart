/// Native HTTP adapters for soliplex_client.
///
/// Provides platform-optimized HTTP adapters:
/// - `CupertinoHttpAdapter` for iOS and macOS using NSURLSession
/// - `createPlatformAdapter` for automatic platform detection
///
/// Example:
/// ```dart
/// import 'package:soliplex_client/soliplex_client.dart';
/// import 'package:soliplex_client_native/soliplex_client_native.dart';
///
/// // Auto-detect platform
/// final adapter = createPlatformAdapter();
///
/// // Or use specific adapter
/// final cupertinoAdapter = CupertinoHttpAdapter();
/// ```
library soliplex_client_native;

export 'src/adapters/adapters.dart';
export 'src/platform/platform.dart';
