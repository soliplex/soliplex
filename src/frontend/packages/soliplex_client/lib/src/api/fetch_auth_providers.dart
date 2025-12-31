import 'package:soliplex_client/src/domain/auth_provider_config.dart';
import 'package:soliplex_client/src/http/http_transport.dart';

/// Fetches available authentication providers from the backend.
///
/// Calls `GET /api/login` (note: outside `/api/v1`) to retrieve
/// the list of configured identity providers.
///
/// Parameters:
/// - [transport]: HTTP transport for making the request.
/// - [baseUrl]: Backend base URL (e.g., "https://api.example.com").
///
/// Returns a list of [AuthProviderConfig] describing available providers.
///
/// Example:
/// ```dart
/// final providers = await fetchAuthProviders(
///   transport: transport,
///   baseUrl: Uri.parse('https://api.example.com'),
/// );
/// for (final provider in providers) {
///   print('${provider.name}: ${provider.serverUrl}');
/// }
/// ```
Future<List<AuthProviderConfig>> fetchAuthProviders({
  required HttpTransport transport,
  required Uri baseUrl,
}) async {
  final uri = baseUrl.resolve('/api/login');
  final response = await transport.request<Map<String, dynamic>>(
    'GET',
    uri,
  );

  // Backend returns a map of provider_id -> provider config
  // Convert to list of AuthProviderConfig
  return response.entries.map((entry) {
    final id = entry.key;
    final data = entry.value as Map<String, dynamic>;
    return AuthProviderConfig(
      id: id,
      name: data['title'] as String,
      serverUrl: data['server_url'] as String,
      clientId: data['client_id'] as String,
      scope: data['scope'] as String,
    );
  }).toList();
}
