import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';

/// PKCE (Proof Key for Code Exchange) challenge pair.
///
/// Used in OAuth 2.0 Authorization Code flow to prevent
/// authorization code interception attacks.
class PkceChallenge {
  const PkceChallenge({
    required this.codeVerifier,
    required this.codeChallenge,
  });

  /// The code verifier - a cryptographically random string.
  /// Stored locally and sent during token exchange.
  final String codeVerifier;

  /// The code challenge - SHA256 hash of the verifier, base64url encoded.
  /// Sent to the authorization server during the initial request.
  final String codeChallenge;

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
      'PkceChallenge(verifier: ${codeVerifier.substring(0, 8)}..., challenge: ${codeChallenge.substring(0, 8)}...)';
}

/// Utilities for PKCE (Proof Key for Code Exchange) in OAuth 2.0.
///
/// Implements RFC 7636 for secure authorization code exchange.
class PkceUtils {
  PkceUtils._();

  static const _codeVerifierLength = 64;
  static const _stateLength = 32;

  /// Characters allowed in code verifier (RFC 7636 Section 4.1).
  /// unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
  static const _unreservedChars =
      'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';

  /// Generate a cryptographically random code verifier.
  ///
  /// The verifier is 64 characters long (within the 43-128 range
  /// required by RFC 7636).
  static String generateCodeVerifier() {
    final random = Random.secure();
    final chars = List.generate(
      _codeVerifierLength,
      (_) => _unreservedChars[random.nextInt(_unreservedChars.length)],
    );
    return chars.join();
  }

  /// Generate a code challenge from a code verifier using S256 method.
  ///
  /// S256: BASE64URL(SHA256(code_verifier))
  static String generateCodeChallenge(String codeVerifier) {
    final bytes = utf8.encode(codeVerifier);
    final digest = sha256.convert(bytes);
    // Base64url encode without padding (per RFC 7636)
    return base64Url.encode(digest.bytes).replaceAll('=', '');
  }

  /// Generate both code verifier and code challenge.
  static PkceChallenge generateChallenge() {
    final verifier = generateCodeVerifier();
    final challenge = generateCodeChallenge(verifier);
    return PkceChallenge(codeVerifier: verifier, codeChallenge: challenge);
  }

  /// Generate a random state parameter for CSRF protection.
  ///
  /// The state is sent with the authorization request and must be
  /// validated when the callback is received.
  static String generateState() {
    final random = Random.secure();
    final bytes = List.generate(_stateLength, (_) => random.nextInt(256));
    // Base64url encode without padding
    return base64Url.encode(bytes).replaceAll('=', '');
  }
}
