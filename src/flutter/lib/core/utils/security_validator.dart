/// Security validator for widget data and network resources.
///
/// Implements security checks:
/// - Domain whitelist for network resources (SSRF prevention)
/// - Payload size validation
/// - Data sanitization
class SecurityValidator {
  SecurityValidator._();

  /// Maximum allowed payload size in bytes (1MB).
  static const int maxPayloadSize = 1024 * 1024;

  /// Allowed domains for network images.
  /// If empty, allows all external domains.
  static const List<String> allowedImageDomains = [
    // Add your CDN domains here if needed
    // 'cdn.example.com',
    // 'images.example.com',
  ];

  /// Validate a URL for network image loading (SSRF prevention).
  static bool isAllowedImageUrl(String url) {
    try {
      final uri = Uri.parse(url);

      // Block non-http(s) schemes
      if (uri.scheme != 'http' && uri.scheme != 'https') {
        return false;
      }

      // Block internal IP addresses
      if (_isInternalHost(uri.host)) {
        return false;
      }

      // Check against domain whitelist
      // If whitelist is empty, allow all external domains
      if (allowedImageDomains.isEmpty) {
        return true;
      }

      return allowedImageDomains.any(
        (domain) => uri.host == domain || uri.host.endsWith('.$domain'),
      );
    } on Object {
      return false;
    }
  }

  /// Check if a host is an internal/private IP address.
  static bool _isInternalHost(String host) {
    // Localhost
    if (host == 'localhost' || host == '127.0.0.1' || host == '::1') {
      return true;
    }

    // Private IP ranges
    final parts = host.split('.');
    if (parts.length == 4) {
      try {
        final a = int.parse(parts[0]);
        final b = int.parse(parts[1]);

        // 10.x.x.x
        if (a == 10) return true;

        // 172.16.x.x - 172.31.x.x
        if (a == 172 && b >= 16 && b <= 31) return true;

        // 192.168.x.x
        if (a == 192 && b == 168) return true;

        // 169.254.x.x (link-local)
        if (a == 169 && b == 254) return true;
      } on Object {
        // Not a valid IP, might be a hostname
      }
    }

    return false;
  }

  /// Validate payload size.
  static bool isValidPayloadSize(int sizeInBytes) {
    return sizeInBytes <= maxPayloadSize;
  }

  /// Sanitize a string to prevent XSS in rendered content.
  static String sanitizeString(String input) {
    // Basic HTML entity encoding
    return input
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#x27;');
  }

  /// Validate numeric range for chart data.
  static bool isValidChartValue(num value) {
    return value.isFinite && !value.isNaN;
  }

  /// Validate a data map for widget rendering.
  static Map<String, dynamic> sanitizeDataMap(Map<String, dynamic> data) {
    return data.map((key, value) {
      if (value is String) {
        return MapEntry(key, sanitizeString(value));
      } else if (value is Map<String, dynamic>) {
        return MapEntry(key, sanitizeDataMap(value));
      } else if (value is List) {
        return MapEntry(key, _sanitizeList(value));
      }
      return MapEntry(key, value);
    });
  }

  static List<dynamic> _sanitizeList(List<dynamic> list) {
    return list.map((item) {
      if (item is String) {
        return sanitizeString(item);
      } else if (item is Map<String, dynamic>) {
        return sanitizeDataMap(item);
      } else if (item is List) {
        return _sanitizeList(item);
      }
      return item;
    }).toList();
  }
}
