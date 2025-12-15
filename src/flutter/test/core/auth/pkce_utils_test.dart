import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex/core/auth/pkce_utils.dart';

void main() {
  group('PkceUtils', () {
    group('generateCodeVerifier', () {
      test('generates string of correct length', () {
        final verifier = PkceUtils.generateCodeVerifier();
        expect(verifier.length, equals(64));
      });

      test('generates unique values', () {
        final verifier1 = PkceUtils.generateCodeVerifier();
        final verifier2 = PkceUtils.generateCodeVerifier();
        expect(verifier1, isNot(equals(verifier2)));
      });

      test('contains only unreserved characters', () {
        final verifier = PkceUtils.generateCodeVerifier();
        // RFC 7636 unreserved chars: A-Z, a-z, 0-9, -, ., _, ~
        final validPattern = RegExp(r'^[A-Za-z0-9\-._~]+$');
        expect(validPattern.hasMatch(verifier), isTrue);
      });

      test('generates valid length per RFC 7636 (43-128 chars)', () {
        final verifier = PkceUtils.generateCodeVerifier();
        expect(verifier.length, greaterThanOrEqualTo(43));
        expect(verifier.length, lessThanOrEqualTo(128));
      });
    });

    group('generateCodeChallenge', () {
      test('generates base64url encoded SHA256 hash', () {
        const verifier = 'test_verifier_string';
        final challenge = PkceUtils.generateCodeChallenge(verifier);

        // Manually compute expected challenge
        final bytes = utf8.encode(verifier);
        final digest = sha256.convert(bytes);
        final expected = base64Url.encode(digest.bytes).replaceAll('=', '');

        expect(challenge, equals(expected));
      });

      test('produces different challenges for different verifiers', () {
        final challenge1 = PkceUtils.generateCodeChallenge('verifier1');
        final challenge2 = PkceUtils.generateCodeChallenge('verifier2');
        expect(challenge1, isNot(equals(challenge2)));
      });

      test('produces same challenge for same verifier', () {
        const verifier = 'consistent_verifier';
        final challenge1 = PkceUtils.generateCodeChallenge(verifier);
        final challenge2 = PkceUtils.generateCodeChallenge(verifier);
        expect(challenge1, equals(challenge2));
      });

      test('does not contain padding characters', () {
        final challenge = PkceUtils.generateCodeChallenge('any_verifier');
        expect(challenge.contains('='), isFalse);
      });

      test('is URL-safe', () {
        final challenge = PkceUtils.generateCodeChallenge('any_verifier');
        // base64url uses - and _ instead of + and /
        expect(challenge.contains('+'), isFalse);
        expect(challenge.contains('/'), isFalse);
      });
    });

    group('generateChallenge', () {
      test('returns PkceChallenge with verifier and challenge', () {
        final pkce = PkceUtils.generateChallenge();
        expect(pkce.codeVerifier, isNotEmpty);
        expect(pkce.codeChallenge, isNotEmpty);
      });

      test('challenge is derived from verifier', () {
        final pkce = PkceUtils.generateChallenge();
        final expectedChallenge = PkceUtils.generateCodeChallenge(
          pkce.codeVerifier,
        );
        expect(pkce.codeChallenge, equals(expectedChallenge));
      });

      test('generates unique challenges each time', () {
        final pkce1 = PkceUtils.generateChallenge();
        final pkce2 = PkceUtils.generateChallenge();
        expect(pkce1.codeVerifier, isNot(equals(pkce2.codeVerifier)));
        expect(pkce1.codeChallenge, isNot(equals(pkce2.codeChallenge)));
      });
    });

    group('generateState', () {
      test('generates non-empty string', () {
        final state = PkceUtils.generateState();
        expect(state, isNotEmpty);
      });

      test('generates unique values', () {
        final state1 = PkceUtils.generateState();
        final state2 = PkceUtils.generateState();
        expect(state1, isNot(equals(state2)));
      });

      test('is URL-safe (base64url encoded)', () {
        final state = PkceUtils.generateState();
        // base64url should not contain + or /
        expect(state.contains('+'), isFalse);
        expect(state.contains('/'), isFalse);
      });

      test('does not contain padding', () {
        final state = PkceUtils.generateState();
        expect(state.contains('='), isFalse);
      });
    });
  });

  group('PkceChallenge', () {
    test('toString masks sensitive data', () {
      const pkce = PkceChallenge(
        codeVerifier: 'verifier12345678901234567890',
        codeChallenge: 'challenge12345678901234567890',
      );
      final str = pkce.toString();
      // Should only show first 8 chars
      expect(str, contains('verifier'));
      expect(str, contains('challeng'));
      expect(str, contains('...'));
      // Should not contain full values
      expect(str.contains('verifier12345678901234567890'), isFalse);
    });
  });
}
