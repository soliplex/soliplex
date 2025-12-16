/// Utility for building URLs with path segments and query parameters.
///
/// Handles URL normalization and encoding automatically.
///
/// Example:
/// ```dart
/// final builder = UrlBuilder('https://api.example.com/v1');
///
/// // Simple path
/// final uri1 = builder.build(path: 'rooms');
/// // https://api.example.com/v1/rooms
///
/// // Path segments
/// final uri2 = builder.build(pathSegments: ['rooms', '123', 'threads']);
/// // https://api.example.com/v1/rooms/123/threads
///
/// // With query parameters
/// final uri3 = builder.build(
///   path: 'search',
///   queryParameters: {'q': 'hello world', 'limit': '10'},
/// );
/// // https://api.example.com/v1/search?q=hello%20world&limit=10
/// ```
class UrlBuilder {
  /// Creates a URL builder with the given [baseUrl].
  ///
  /// The base URL should include the scheme (https://) and may include
  /// a path prefix (e.g., '/v1'). Trailing slashes are normalized.
  ///
  /// Throws [FormatException] if [baseUrl] is not a valid URL.
  UrlBuilder(String baseUrl) : _baseUri = Uri.parse(baseUrl) {
    if (!_baseUri.hasScheme) {
      throw FormatException('Base URL must have a scheme: $baseUrl');
    }
  }

  final Uri _baseUri;

  /// The base URL as a string.
  String get baseUrl => _baseUri.toString();

  /// Builds a URI from the base URL with optional path and query parameters.
  ///
  /// Parameters:
  /// - [path]: A single path segment to append (e.g., 'rooms')
  /// - [pathSegments]: Multiple path segments to append
  ///   (e.g., `['rooms', '123']`)
  /// - [queryParameters]: Query parameters to add to the URL
  ///
  /// If both [path] and [pathSegments] are provided, they are combined
  /// with [path] first, followed by [pathSegments].
  ///
  /// Path segments are automatically normalized:
  /// - Leading and trailing slashes are stripped
  /// - Empty segments are ignored
  Uri build({
    String? path,
    List<String>? pathSegments,
    Map<String, String>? queryParameters,
  }) {
    // Start with base URI path segments
    final segments = <String>[
      ..._baseUri.pathSegments.where((s) => s.isNotEmpty),
    ];

    // Add single path (split by '/')
    if (path != null && path.isNotEmpty) {
      final normalized = _normalizePath(path);
      if (normalized.isNotEmpty) {
        segments.addAll(normalized.split('/').where((s) => s.isNotEmpty));
      }
    }

    // Add path segments
    if (pathSegments != null) {
      for (final segment in pathSegments) {
        if (segment.isNotEmpty) {
          // Handle segments that contain slashes
          final parts = segment.split('/').where((s) => s.isNotEmpty);
          segments.addAll(parts);
        }
      }
    }

    // Build the URI
    return _baseUri.replace(
      pathSegments: segments,
      queryParameters:
          (queryParameters?.isNotEmpty ?? false) ? queryParameters : null,
    );
  }

  /// Normalizes a path by removing leading and trailing slashes.
  String _normalizePath(String path) {
    var result = path;
    while (result.startsWith('/')) {
      result = result.substring(1);
    }
    while (result.endsWith('/')) {
      result = result.substring(0, result.length - 1);
    }
    return result;
  }

  @override
  String toString() => 'UrlBuilder($baseUrl)';
}
