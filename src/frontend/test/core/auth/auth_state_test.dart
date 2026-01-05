import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';

void main() {
  group('Unauthenticated', () {
    test('instances are equal', () {
      const a = Unauthenticated();
      const b = Unauthenticated();

      expect(a, equals(b));
      expect(a.hashCode, equals(b.hashCode));
    });

    test('is not equal to other AuthState types', () {
      const unauthenticated = Unauthenticated();
      const loading = AuthLoading();

      expect(unauthenticated, isNot(equals(loading)));
    });
  });

  group('AuthLoading', () {
    test('instances are equal', () {
      const a = AuthLoading();
      const b = AuthLoading();

      expect(a, equals(b));
      expect(a.hashCode, equals(b.hashCode));
    });
  });

  group('Authenticated', () {
    final defaultExpiresAt = DateTime(2025, 12, 31, 12);

    Authenticated createAuth({
      String accessToken = 'access',
      String refreshToken = 'refresh',
      DateTime? expiresAt,
      String issuerId = 'issuer-1',
      String issuerDiscoveryUrl = 'https://idp.example.com/.well-known',
      String? idToken = 'id-token',
      Map<String, dynamic>? userInfo,
    }) {
      return Authenticated(
        accessToken: accessToken,
        refreshToken: refreshToken,
        expiresAt: expiresAt ?? defaultExpiresAt,
        issuerId: issuerId,
        issuerDiscoveryUrl: issuerDiscoveryUrl,
        idToken: idToken,
        userInfo: userInfo,
      );
    }

    group('equality', () {
      test('equal when all fields match', () {
        final a = createAuth();
        final b = createAuth();

        expect(a, equals(b));
        expect(a.hashCode, equals(b.hashCode));
      });

      test('not equal when accessToken differs', () {
        final a = createAuth(accessToken: 'token-a');
        final b = createAuth(accessToken: 'token-b');

        expect(a, isNot(equals(b)));
      });

      test('not equal when refreshToken differs', () {
        final a = createAuth(refreshToken: 'refresh-a');
        final b = createAuth(refreshToken: 'refresh-b');

        expect(a, isNot(equals(b)));
      });

      test('not equal when expiresAt differs', () {
        final a = createAuth(expiresAt: DateTime(2025, 1, 1, 10));
        final b = createAuth(expiresAt: DateTime(2025, 1, 2, 10));

        expect(a, isNot(equals(b)));
      });

      test('not equal when issuerId differs', () {
        final a = createAuth(issuerId: 'issuer-a');
        final b = createAuth(issuerId: 'issuer-b');

        expect(a, isNot(equals(b)));
      });

      test('not equal when idToken differs', () {
        final a = createAuth(idToken: 'id-a');
        final b = createAuth(idToken: 'id-b');

        expect(a, isNot(equals(b)));
      });

      test('equal when only userInfo differs', () {
        final a = createAuth(userInfo: {'name': 'Alice'});
        final b = createAuth(userInfo: {'name': 'Bob'});

        expect(a, equals(b));
      });

      test('equal when one has userInfo and other does not', () {
        final a = createAuth(userInfo: {'name': 'Alice'});
        final b = createAuth();

        expect(a, equals(b));
      });
    });

    group('isExpired', () {
      test('returns true when expiresAt is in the past', () {
        final auth = createAuth(
          expiresAt: DateTime.now().subtract(const Duration(minutes: 5)),
        );

        expect(auth.isExpired, isTrue);
      });

      test('returns false when expiresAt is in the future', () {
        final auth = createAuth(
          expiresAt: DateTime.now().add(const Duration(hours: 1)),
        );

        expect(auth.isExpired, isFalse);
      });
    });

    group('needsRefresh', () {
      test('returns true when within 1 minute of expiry', () {
        final auth = createAuth(
          expiresAt: DateTime.now().add(const Duration(seconds: 30)),
        );

        expect(auth.needsRefresh, isTrue);
      });

      test('returns false when more than 1 minute until expiry', () {
        final auth = createAuth(
          expiresAt: DateTime.now().add(const Duration(minutes: 5)),
        );

        expect(auth.needsRefresh, isFalse);
      });

      test('returns true when already expired', () {
        final auth = createAuth(
          expiresAt: DateTime.now().subtract(const Duration(minutes: 1)),
        );

        expect(auth.needsRefresh, isTrue);
      });
    });
  });
}
