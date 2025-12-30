import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('UserInfo', () {
    test('creates with required fields', () {
      const user = UserInfo(id: 'user-123');

      expect(user.id, equals('user-123'));
      expect(user.email, isNull);
      expect(user.name, isNull);
    });

    test('creates with all fields', () {
      const user = UserInfo(
        id: 'user-123',
        email: 'user@example.com',
        name: 'Test User',
      );

      expect(user.id, equals('user-123'));
      expect(user.email, equals('user@example.com'));
      expect(user.name, equals('Test User'));
    });

    group('displayName', () {
      test('returns name when available', () {
        const user = UserInfo(
          id: 'user-123',
          email: 'user@example.com',
          name: 'Test User',
        );

        expect(user.displayName, equals('Test User'));
      });

      test('returns email when name is null', () {
        const user = UserInfo(
          id: 'user-123',
          email: 'user@example.com',
        );

        expect(user.displayName, equals('user@example.com'));
      });

      test('returns id when name and email are null', () {
        const user = UserInfo(id: 'user-123');

        expect(user.displayName, equals('user-123'));
      });
    });

    group('copyWith', () {
      test('creates modified copy', () {
        const user = UserInfo(id: 'user-123');
        final modified = user.copyWith(email: 'new@example.com');

        expect(modified.id, equals('user-123'));
        expect(modified.email, equals('new@example.com'));
        expect(user.email, isNull);
      });

      test('creates copy with all fields modified', () {
        const user = UserInfo(id: 'user-123');
        final modified = user.copyWith(
          id: 'user-456',
          email: 'new@example.com',
          name: 'New User',
        );

        expect(modified.id, equals('user-456'));
        expect(modified.email, equals('new@example.com'));
        expect(modified.name, equals('New User'));
      });
    });

    group('equality', () {
      test('equal when all fields match', () {
        const user1 = UserInfo(id: 'user-123', name: 'User 1');
        const user2 = UserInfo(id: 'user-123', name: 'User 1');

        expect(user1, equals(user2));
      });

      test('not equal when fields differ', () {
        const user1 = UserInfo(id: 'user-123', name: 'User 1');
        const user2 = UserInfo(id: 'user-123', name: 'User 2');
        const user3 = UserInfo(id: 'user-456', name: 'User 1');

        expect(user1, isNot(equals(user2)));
        expect(user1, isNot(equals(user3)));
      });

      test('identical returns true', () {
        const user = UserInfo(id: 'user-123');
        expect(user == user, isTrue);
      });
    });

    test('hashCode consistent with equality', () {
      const user1 = UserInfo(id: 'user-123', name: 'User 1');
      const user2 = UserInfo(id: 'user-123', name: 'User 1');

      expect(user1.hashCode, equals(user2.hashCode));
    });

    test('toString includes id', () {
      const user = UserInfo(
        id: 'user-123',
        email: 'user@example.com',
        name: 'Test User',
      );

      final str = user.toString();

      expect(str, contains('user-123'));
    });

    group('JSON serialization', () {
      test('toJson converts to map', () {
        const user = UserInfo(
          id: 'user-123',
          email: 'user@example.com',
          name: 'Test User',
        );

        final json = user.toJson();

        expect(json['id'], equals('user-123'));
        expect(json['email'], equals('user@example.com'));
        expect(json['name'], equals('Test User'));
      });

      test('fromJson parses map', () {
        final json = {
          'id': 'user-123',
          'email': 'user@example.com',
          'name': 'Test User',
        };

        final user = UserInfo.fromJson(json);

        expect(user.id, equals('user-123'));
        expect(user.email, equals('user@example.com'));
        expect(user.name, equals('Test User'));
      });

      test('fromJson handles minimal fields', () {
        final json = {'id': 'user-123'};

        final user = UserInfo.fromJson(json);

        expect(user.id, equals('user-123'));
        expect(user.email, isNull);
        expect(user.name, isNull);
      });

      test('roundtrip preserves data', () {
        const original = UserInfo(
          id: 'user-123',
          email: 'user@example.com',
          name: 'Test User',
        );

        final restored = UserInfo.fromJson(original.toJson());

        expect(restored, equals(original));
      });
    });

    group('fromOidcClaims', () {
      test('parses standard OIDC claims', () {
        final claims = {
          'sub': 'user-123',
          'email': 'user@example.com',
          'name': 'Test User',
        };

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.id, equals('user-123'));
        expect(user.email, equals('user@example.com'));
        expect(user.name, equals('Test User'));
      });

      test('uses id as fallback for sub', () {
        final claims = {
          'id': 'user-456',
          'email': 'user@example.com',
        };

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.id, equals('user-456'));
      });

      test('prefers sub over id', () {
        final claims = {
          'sub': 'sub-value',
          'id': 'id-value',
        };

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.id, equals('sub-value'));
      });

      test('throws AuthErrorConfiguration when no id fields present', () {
        final claims = <String, dynamic>{'email': 'user@example.com'};

        expect(
          () => UserInfo.fromOidcClaims(claims),
          throwsA(isA<AuthErrorConfiguration>()),
        );
      });

      test('throws AuthErrorConfiguration when sub is empty string', () {
        final claims = <String, dynamic>{
          'sub': '',
          'email': 'user@example.com',
        };

        expect(
          () => UserInfo.fromOidcClaims(claims),
          throwsA(isA<AuthErrorConfiguration>()),
        );
      });

      test('throws AuthErrorConfiguration when id is empty string', () {
        final claims = <String, dynamic>{
          'id': '',
          'email': 'user@example.com',
        };

        expect(
          () => UserInfo.fromOidcClaims(claims),
          throwsA(isA<AuthErrorConfiguration>()),
        );
      });

      test('builds name from given_name and family_name', () {
        final claims = {
          'sub': 'user-123',
          'given_name': 'John',
          'family_name': 'Doe',
        };

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.name, equals('John Doe'));
      });

      test('uses only given_name when family_name missing', () {
        final claims = {
          'sub': 'user-123',
          'given_name': 'John',
        };

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.name, equals('John'));
      });

      test('uses only family_name when given_name missing', () {
        final claims = {
          'sub': 'user-123',
          'family_name': 'Doe',
        };

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.name, equals('Doe'));
      });

      test('prefers name over given_name/family_name', () {
        final claims = {
          'sub': 'user-123',
          'name': 'Full Name',
          'given_name': 'John',
          'family_name': 'Doe',
        };

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.name, equals('Full Name'));
      });

      test('handles minimal claims', () {
        final claims = {'sub': 'user-123'};

        final user = UserInfo.fromOidcClaims(claims);

        expect(user.id, equals('user-123'));
        expect(user.email, isNull);
        expect(user.name, isNull);
      });
    });
  });
}
