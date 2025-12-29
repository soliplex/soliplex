import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('AuthToken', () {
    test('creates with required fields', () {
      final token = AuthToken(
        accessToken: 'access-123',
        expiresAt: DateTime.utc(2025, 1, 1, 12),
      );

      expect(token.accessToken, equals('access-123'));
      expect(token.expiresAt, equals(DateTime.utc(2025, 1, 1, 12)));
      expect(token.refreshToken, isNull);
      expect(token.idToken, isNull);
    });

    test('creates with all fields', () {
      final token = AuthToken(
        accessToken: 'access-123',
        refreshToken: 'refresh-456',
        expiresAt: DateTime.utc(2025, 1, 1, 12),
        idToken: 'id-789',
      );

      expect(token.accessToken, equals('access-123'));
      expect(token.refreshToken, equals('refresh-456'));
      expect(token.expiresAt, equals(DateTime.utc(2025, 1, 1, 12)));
      expect(token.idToken, equals('id-789'));
    });

    group('isExpired', () {
      test('returns true when token has expired', () {
        final expiredToken = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2020),
        );

        expect(expiredToken.isExpired, isTrue);
      });

      test('returns false when token has not expired', () {
        final validToken = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.now().toUtc().add(const Duration(hours: 1)),
        );

        expect(validToken.isExpired, isFalse);
      });
    });

    test('defaultRefreshBuffer is 5 minutes', () {
      expect(
        AuthToken.defaultRefreshBuffer,
        equals(const Duration(minutes: 5)),
      );
    });

    group('needsRefresh', () {
      test('returns true when token expires within 5 minutes', () {
        final nearExpiryToken = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 3)),
        );

        expect(nearExpiryToken.needsRefresh, isTrue);
      });

      test('returns false when token has more than 5 minutes left', () {
        final validToken = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 10)),
        );

        expect(validToken.needsRefresh, isFalse);
      });

      test('returns true when token is already expired', () {
        final expiredToken = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2020),
        );

        expect(expiredToken.needsRefresh, isTrue);
      });
    });

    group('needsRefreshWithin', () {
      test('returns true when token expires within custom buffer', () {
        final token = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 8)),
        );

        expect(token.needsRefreshWithin(const Duration(minutes: 10)), isTrue);
        expect(token.needsRefreshWithin(const Duration(minutes: 5)), isFalse);
      });
    });

    group('canRefresh', () {
      test('returns true when refresh token is present', () {
        final token = AuthToken(
          accessToken: 'access-123',
          refreshToken: 'refresh-456',
          expiresAt: DateTime.utc(2025),
        );

        expect(token.canRefresh, isTrue);
      });

      test('returns false when refresh token is absent', () {
        final token = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );

        expect(token.canRefresh, isFalse);
      });
    });

    group('copyWith', () {
      test('creates modified copy', () {
        final token = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final modified = token.copyWith(accessToken: 'new-access');

        expect(modified.accessToken, equals('new-access'));
        expect(modified.expiresAt, equals(DateTime.utc(2025)));
        expect(token.accessToken, equals('access-123'));
      });

      test('creates copy with all fields modified', () {
        final token = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final modified = token.copyWith(
          accessToken: 'new-access',
          refreshToken: 'new-refresh',
          expiresAt: DateTime.utc(2026),
          idToken: 'new-id',
        );

        expect(modified.accessToken, equals('new-access'));
        expect(modified.refreshToken, equals('new-refresh'));
        expect(modified.expiresAt, equals(DateTime.utc(2026)));
        expect(modified.idToken, equals('new-id'));
      });
    });

    group('equality', () {
      test('equal when all fields match', () {
        final token1 = AuthToken(
          accessToken: 'access-123',
          refreshToken: 'refresh-456',
          expiresAt: DateTime.utc(2025),
          idToken: 'id-789',
        );
        final token2 = AuthToken(
          accessToken: 'access-123',
          refreshToken: 'refresh-456',
          expiresAt: DateTime.utc(2025),
          idToken: 'id-789',
        );

        expect(token1, equals(token2));
      });

      test('not equal when fields differ', () {
        final token1 = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final token2 = AuthToken(
          accessToken: 'access-456',
          expiresAt: DateTime.utc(2025),
        );

        expect(token1, isNot(equals(token2)));
      });
    });

    test('hashCode consistent with equality', () {
      final token1 = AuthToken(
        accessToken: 'access-123',
        refreshToken: 'refresh-456',
        expiresAt: DateTime.utc(2025),
        idToken: 'id-789',
      );
      final token2 = AuthToken(
        accessToken: 'access-123',
        refreshToken: 'refresh-456',
        expiresAt: DateTime.utc(2025),
        idToken: 'id-789',
      );

      expect(token1.hashCode, equals(token2.hashCode));
    });

    test('toString includes token info without exposing secrets', () {
      final token = AuthToken(
        accessToken: 'access-123',
        refreshToken: 'refresh-456',
        expiresAt: DateTime.utc(2025, 1, 1, 12),
      );

      final str = token.toString();

      expect(str, contains('AuthToken'));
      expect(str, contains('expiresAt'));
      // Should not expose actual tokens
      expect(str, isNot(contains('access-123')));
      expect(str, isNot(contains('refresh-456')));
    });

    group('JSON serialization', () {
      test('toJson converts to map', () {
        final token = AuthToken(
          accessToken: 'access-123',
          refreshToken: 'refresh-456',
          expiresAt: DateTime.utc(2025, 1, 1, 12),
          idToken: 'id-789',
        );

        final json = token.toJson();

        expect(json['access_token'], equals('access-123'));
        expect(json['refresh_token'], equals('refresh-456'));
        expect(json['expires_at'], equals('2025-01-01T12:00:00.000Z'));
        expect(json['id_token'], equals('id-789'));
      });

      test('fromJson parses map', () {
        final json = {
          'access_token': 'access-123',
          'refresh_token': 'refresh-456',
          'expires_at': '2025-01-01T12:00:00.000Z',
          'id_token': 'id-789',
        };

        final token = AuthToken.fromJson(json);

        expect(token.accessToken, equals('access-123'));
        expect(token.refreshToken, equals('refresh-456'));
        expect(token.expiresAt, equals(DateTime.utc(2025, 1, 1, 12)));
        expect(token.idToken, equals('id-789'));
      });

      test('fromJson handles minimal fields', () {
        final json = {
          'access_token': 'access-123',
          'expires_at': '2025-01-01T12:00:00.000Z',
        };

        final token = AuthToken.fromJson(json);

        expect(token.accessToken, equals('access-123'));
        expect(token.refreshToken, isNull);
        expect(token.idToken, isNull);
      });

      test('roundtrip preserves data', () {
        final original = AuthToken(
          accessToken: 'access-123',
          refreshToken: 'refresh-456',
          expiresAt: DateTime.utc(2025, 1, 1, 12),
          idToken: 'id-789',
        );

        final restored = AuthToken.fromJson(original.toJson());

        expect(restored, equals(original));
      });
    });
  });
}
