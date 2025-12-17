// ignore_for_file: avoid_print
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/soliplex_client_native.dart';

/// Tests for platform detection.
///
/// Note: Tests that instantiate CupertinoHttpAdapter directly require native
/// libraries and can only run in a real Flutter app environment (macOS/iOS).
/// In the standard `flutter test` environment, these tests are skipped because
/// the cupertino_http FFI bindings aren't available.
void main() {
  group('createPlatformAdapter', () {
    // Check if we can load native libraries (only possible in macOS/iOS app)
    bool canLoadNativeLibraries() {
      if (!Platform.isMacOS && !Platform.isIOS) {
        return false;
      }
      try {
        // Try to create a CupertinoHttpAdapter - will throw if native libs
        // aren't available
        CupertinoHttpAdapter().close();
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
      'returns HttpClientAdapter',
      skip: skipNativeTests,
      () {
        final adapter = createPlatformAdapter();
        expect(adapter, isA<HttpClientAdapter>());
        adapter.close();
      },
    );

    test(
      'accepts custom timeout',
      skip: skipNativeTests,
      () {
        final adapter = createPlatformAdapter(
          defaultTimeout: const Duration(seconds: 60),
        );
        expect(adapter, isA<HttpClientAdapter>());
        adapter.close();
      },
    );

    test(
      'returns CupertinoHttpAdapter on macOS',
      skip: !Platform.isMacOS || skipNativeTests != null
          ? 'Requires macOS with native libraries'
          : null,
      () {
        final adapter = createPlatformAdapter();
        expect(adapter, isA<CupertinoHttpAdapter>());
        adapter.close();
      },
    );

    test(
      'returns CupertinoHttpAdapter on iOS',
      skip: !Platform.isIOS ? 'Not running on iOS' : skipNativeTests,
      () {
        final adapter = createPlatformAdapter();
        expect(adapter, isA<CupertinoHttpAdapter>());
        adapter.close();
      },
    );

    test(
      'returns DartHttpAdapter on non-Apple platforms',
      skip: Platform.isMacOS || Platform.isIOS
          ? 'Running on Apple platform'
          : null,
      () {
        final adapter = createPlatformAdapter();
        expect(adapter, isA<DartHttpAdapter>());
        adapter.close();
      },
    );

    test(
      'CupertinoHttpAdapter respects custom timeout',
      skip: (!Platform.isMacOS && !Platform.isIOS) || skipNativeTests != null
          ? 'Requires Apple platform with native libraries'
          : null,
      () {
        final adapter = createPlatformAdapter(
          defaultTimeout: const Duration(seconds: 45),
        );
        expect(adapter, isA<CupertinoHttpAdapter>());
        expect(
          (adapter as CupertinoHttpAdapter).defaultTimeout,
          equals(const Duration(seconds: 45)),
        );
        adapter.close();
      },
    );
  });
}
