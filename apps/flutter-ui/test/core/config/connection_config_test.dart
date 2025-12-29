import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/config/connection_config.dart';

void main() {
  group('ConnectionConfig', () {
    group('constructor', () {
      test('creates config with default values', () {
        const config = ConnectionConfig();

        expect(config.roomInactivityTimeout, equals(const Duration(hours: 24)));
        expect(config.serverInactivityTimeout, equals(const Duration(days: 7)));
        expect(config.maxBackgroundedSessionsPerServer, equals(5));
        expect(config.cleanupInterval, equals(const Duration(minutes: 5)));
        expect(config.keepAlive, isFalse);
      });

      test('creates config with custom values', () {
        const config = ConnectionConfig(
          roomInactivityTimeout: Duration(hours: 1),
          serverInactivityTimeout: Duration(days: 1),
          maxBackgroundedSessionsPerServer: 3,
          cleanupInterval: Duration(minutes: 1),
          keepAlive: true,
        );

        expect(config.roomInactivityTimeout, equals(const Duration(hours: 1)));
        expect(config.serverInactivityTimeout, equals(const Duration(days: 1)));
        expect(config.maxBackgroundedSessionsPerServer, equals(3));
        expect(config.cleanupInterval, equals(const Duration(minutes: 1)));
        expect(config.keepAlive, isTrue);
      });
    });

    group('static presets', () {
      test('defaultConfig has sensible defaults', () {
        const config = ConnectionConfig.defaultConfig;

        expect(config.roomInactivityTimeout, equals(const Duration(hours: 24)));
        expect(config.serverInactivityTimeout, equals(const Duration(days: 7)));
        expect(config.maxBackgroundedSessionsPerServer, equals(5));
        expect(config.keepAlive, isFalse);
      });

      test('noCleanup has keepAlive true', () {
        const config = ConnectionConfig.noCleanup;

        expect(config.keepAlive, isTrue);
      });

      test('aggressive has short timeouts', () {
        const config = ConnectionConfig.aggressive;

        expect(
          config.roomInactivityTimeout,
          equals(const Duration(minutes: 30)),
        );
        expect(
          config.serverInactivityTimeout,
          equals(const Duration(hours: 1)),
        );
        expect(config.maxBackgroundedSessionsPerServer, equals(2));
        expect(config.cleanupInterval, equals(const Duration(minutes: 1)));
        expect(config.keepAlive, isFalse);
      });
    });

    group('equality', () {
      test('equal configs have same values', () {
        const config1 = ConnectionConfig(
          roomInactivityTimeout: Duration(hours: 1),
          serverInactivityTimeout: Duration(days: 1),
        );
        const config2 = ConnectionConfig(
          roomInactivityTimeout: Duration(hours: 1),
          serverInactivityTimeout: Duration(days: 1),
        );

        expect(config1, equals(config2));
      });

      test('different configs are not equal', () {
        const config1 = ConnectionConfig(
          roomInactivityTimeout: Duration(hours: 1),
        );
        const config2 = ConnectionConfig(
          roomInactivityTimeout: Duration(hours: 2),
        );

        expect(config1, isNot(equals(config2)));
      });

      test('identical configs are equal', () {
        const config = ConnectionConfig.defaultConfig;

        expect(config == config, isTrue);
      });
    });

    group('hashCode', () {
      test('equal configs have same hashCode', () {
        const config1 = ConnectionConfig(
          roomInactivityTimeout: Duration(hours: 1),
        );
        const config2 = ConnectionConfig(
          roomInactivityTimeout: Duration(hours: 1),
        );

        expect(config1.hashCode, equals(config2.hashCode));
      });

      test('hashCode is consistent', () {
        const config = ConnectionConfig.defaultConfig;
        final hash1 = config.hashCode;
        final hash2 = config.hashCode;

        expect(hash1, equals(hash2));
      });
    });

    group('copyWith', () {
      test('copies with new roomInactivityTimeout', () {
        const original = ConnectionConfig.defaultConfig;
        final copied = original.copyWith(
          roomInactivityTimeout: const Duration(hours: 1),
        );

        expect(copied.roomInactivityTimeout, equals(const Duration(hours: 1)));
        expect(
          copied.serverInactivityTimeout,
          equals(original.serverInactivityTimeout),
        );
      });

      test('copies with new serverInactivityTimeout', () {
        const original = ConnectionConfig.defaultConfig;
        final copied = original.copyWith(
          serverInactivityTimeout: const Duration(days: 1),
        );

        expect(copied.serverInactivityTimeout, equals(const Duration(days: 1)));
        expect(
          copied.roomInactivityTimeout,
          equals(original.roomInactivityTimeout),
        );
      });

      test('copies with new maxBackgroundedSessionsPerServer', () {
        const original = ConnectionConfig.defaultConfig;
        final copied = original.copyWith(maxBackgroundedSessionsPerServer: 10);

        expect(copied.maxBackgroundedSessionsPerServer, equals(10));
      });

      test('copies with new cleanupInterval', () {
        const original = ConnectionConfig.defaultConfig;
        final copied = original.copyWith(
          cleanupInterval: const Duration(minutes: 10),
        );

        expect(copied.cleanupInterval, equals(const Duration(minutes: 10)));
      });

      test('copies with new keepAlive', () {
        const original = ConnectionConfig.defaultConfig;
        final copied = original.copyWith(keepAlive: true);

        expect(copied.keepAlive, isTrue);
      });

      test('copies with all new values', () {
        const original = ConnectionConfig.defaultConfig;
        final copied = original.copyWith(
          roomInactivityTimeout: const Duration(hours: 1),
          serverInactivityTimeout: const Duration(days: 1),
          maxBackgroundedSessionsPerServer: 3,
          cleanupInterval: const Duration(minutes: 1),
          keepAlive: true,
        );

        expect(copied.roomInactivityTimeout, equals(const Duration(hours: 1)));
        expect(copied.serverInactivityTimeout, equals(const Duration(days: 1)));
        expect(copied.maxBackgroundedSessionsPerServer, equals(3));
        expect(copied.cleanupInterval, equals(const Duration(minutes: 1)));
        expect(copied.keepAlive, isTrue);
      });

      test('copies with no changes', () {
        const original = ConnectionConfig.defaultConfig;
        final copied = original.copyWith();

        expect(copied, equals(original));
      });
    });

    group('toString', () {
      test('returns readable string', () {
        const config = ConnectionConfig.defaultConfig;
        final str = config.toString();

        expect(str, contains('roomInactivity'));
        expect(str, contains('serverInactivity'));
        expect(str, contains('maxBackgrounded'));
        expect(str, contains('cleanup'));
        expect(str, contains('keepAlive'));
      });
    });
  });
}
