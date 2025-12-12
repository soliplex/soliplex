import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../client/client.dart';

/// Provider for the SoliplexClient instance.
///
/// This is app-scoped and manages the connection to the backend.
final soliplexClientProvider = Provider<SoliplexClient>((ref) {
  final client = SoliplexClient();
  ref.onDispose(() => client.dispose());
  return client;
});

/// Provider for the current server URL.
final serverUrlProvider = StateProvider<String>((ref) {
  return 'http://localhost:8000';
});

/// Provider to configure the client with the current server URL.
///
/// Call this when the server URL changes to reconfigure the client.
final configureClientProvider = Provider<void Function(String, {Map<String, String>? headers})>((ref) {
  final client = ref.watch(soliplexClientProvider);
  return (String baseUrl, {Map<String, String>? headers}) {
    client.configure(baseUrl, headers: headers);
    ref.read(serverUrlProvider.notifier).state = baseUrl;
  };
});
