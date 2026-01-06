import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';

/// Provider for backend health status.
///
/// Checks if the backend is reachable by making a request to the
/// `/api/ok` endpoint. This provider is useful for:
/// - Showing a warning banner if backend is down
/// - Preventing unnecessary API calls when backend is unreachable
/// - Displaying connection status in settings
///
/// **Usage Example**:
/// ```dart
/// final healthAsync = ref.watch(backendHealthProvider);
/// healthAsync.when(
///   data: (isHealthy) => isHealthy
///       ? const Icon(Icons.check_circle, color: Colors.green)
///       : const Icon(Icons.error, color: Colors.red),
///   loading: () => const CircularProgressIndicator(),
///   error: (_, __) => const Icon(Icons.error, color: Colors.red),
/// );
/// ```
///
/// **Timeout**: Health checks timeout after 5 seconds to avoid blocking
/// the UI for too long.
///
/// **Refresh**: Use `ref.refresh(backendHealthProvider)` to manually
/// re-check backend health.
///
/// **Observability**: Uses [baseHttpClientProvider] so health checks appear
/// in the HTTP inspector. Does not use authenticated client since `/api/ok`
/// doesn't require authentication.
final backendHealthProvider = FutureProvider<bool>((ref) async {
  final config = ref.watch(configProvider);
  final httpClient = ref.watch(baseHttpClientProvider);

  try {
    final response = await httpClient.request(
      'GET',
      Uri.parse('${config.baseUrl}/api/ok'),
      timeout: const Duration(seconds: 5),
    );

    return response.statusCode == 200;
  } catch (e) {
    // Any error (timeout, network, etc.) means backend is unhealthy
    return false;
  }
});
