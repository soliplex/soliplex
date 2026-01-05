import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/soliplex_client_native.dart';

/// Tests for platform detection.
///
/// Note: Tests that instantiate CupertinoHttpClient directly require native
/// libraries and can only run in a real Flutter app environment (macOS/iOS).
/// In the standard `flutter test` environment, these tests are skipped because
/// the cupertino_http FFI bindings aren't available.
void main() {
  group('createPlatformClient', () {
    // Check if we can load native libraries (only possible in macOS/iOS app)
    bool canLoadNativeLibraries() {
      if (!Platform.isMacOS && !Platform.isIOS) {
        return false;
      }
      try {
        // Try to create a CupertinoHttpClient - will throw if native libs
        // aren't available
        CupertinoHttpClient().close();
        return true;
      } catch (e) {
        // Native libraries not available (running in pure Dart test env)
        return false;
      }
    }

    final hasNativeLibs = canLoadNativeLibraries();
    final skipNativeTests =
        !hasNativeLibs ? 'Native libraries not available in test env' : null;

    test(
      'returns SoliplexHttpClient',
      skip: skipNativeTests,
      () {
        final client = createPlatformClient();
        expect(client, isA<SoliplexHttpClient>());
        client.close();
      },
    );

    test(
      'accepts custom timeout',
      skip: skipNativeTests,
      () {
        final client = createPlatformClient(
          defaultTimeout: const Duration(seconds: 60),
        );
        expect(client, isA<SoliplexHttpClient>());
        client.close();
      },
    );

    test(
      'returns CupertinoHttpClient on macOS',
      skip: !Platform.isMacOS || skipNativeTests != null
          ? 'Requires macOS with native libraries'
          : null,
      () {
        final client = createPlatformClient();
        expect(client, isA<CupertinoHttpClient>());
        client.close();
      },
    );

    test(
      'returns CupertinoHttpClient on iOS',
      skip: !Platform.isIOS ? 'Not running on iOS' : skipNativeTests,
      () {
        final client = createPlatformClient();
        expect(client, isA<CupertinoHttpClient>());
        client.close();
      },
    );

    test(
      'returns DartHttpClient on non-Apple platforms',
      skip: Platform.isMacOS || Platform.isIOS
          ? 'Running on Apple platform'
          : null,
      () {
        final client = createPlatformClient();
        expect(client, isA<DartHttpClient>());
        client.close();
      },
    );

    test(
      'CupertinoHttpClient respects custom timeout',
      skip: (!Platform.isMacOS && !Platform.isIOS) || skipNativeTests != null
          ? 'Requires Apple platform with native libraries'
          : null,
      () {
        final client = createPlatformClient(
          defaultTimeout: const Duration(seconds: 45),
        );
        expect(client, isA<CupertinoHttpClient>());
        expect(
          (client as CupertinoHttpClient).defaultTimeout,
          equals(const Duration(seconds: 45)),
        );
        client.close();
      },
    );
  });
}
