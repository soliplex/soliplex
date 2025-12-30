import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/auth_orchestrator.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

/// Login screen for server and provider selection.
///
/// Flow:
/// 1. User enters server URL
/// 2. User taps "Connect" to probe server for auth providers
/// 3. Server returns list of OIDC providers
/// 4. User selects a provider to initiate login
/// 5. App discovers OIDC config and starts auth flow
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _serverUrlController = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _syncControllerFromState();
      ref.listenManual(
        appStateProvider.select(_extractServerId),
        (previous, next) {
          if (next != null &&
              next.isNotEmpty &&
              _serverUrlController.text != next) {
            _serverUrlController.text = next;
          }
        },
      );
    });
  }

  /// Extracts serverId from state via pattern matching.
  static String? _extractServerId(AppState state) => switch (state) {
        AppStateNoServer() => null,
        AppStateProbing(:final serverId) => serverId,
        AppStateNeedsAuth(:final serverId) => serverId,
        AppStateAuthenticating(:final serverId) => serverId,
        AppStateReady(:final serverId) => serverId,
        AppStateError(:final serverId) => serverId,
      };

  /// Extracts providers from state via pattern matching.
  static List<OIDCAuthSystem> _extractProviders(AppState state) {
    return switch (state) {
      AppStateNeedsAuth(:final providers) => providers,
      AppStateAuthenticating(:final providers) => providers,
      AppStateError(:final providers) => providers,
      _ => const [],
    };
  }

  void _syncControllerFromState() {
    final appState = ref.read(appStateProvider);
    final serverId = _extractServerId(appState);
    _serverUrlController.text = serverId != null && serverId.isNotEmpty
        ? serverId
        : ref.read(configProvider).baseUrl;
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    super.dispose();
  }

  Future<void> _probeServer() async {
    if (!_formKey.currentState!.validate()) return;

    final serverUrl = _serverUrlController.text.trim();
    final notifier = ref.read(appStateProvider.notifier)..beginProbe(serverUrl);

    final orchestrator = ref.read(authOrchestratorProvider);
    final result = await orchestrator.probeServer(serverUrl);
    switch (result) {
      case ProbeSuccess(:final providers):
        notifier.setNeedsAuth(serverId: serverUrl, providers: providers);
      case ProbeFailure(:final message):
        notifier.setError(message: message, serverId: serverUrl);
    }
  }

  Future<void> _login(OIDCAuthSystem authSystem) async {
    final appState = ref.read(appStateProvider);

    // Extract serverId and providers - login only valid from certain states
    final (serverId, providers) = switch (appState) {
      AppStateNeedsAuth(:final serverId, :final providers) => (
          serverId,
          providers,
        ),
      AppStateError(:final serverId?, :final providers)
          when providers.isNotEmpty =>
        (serverId, providers),
      _ => (null, null),
    };

    if (serverId == null || providers == null) return;

    final notifier = ref.read(appStateProvider.notifier)
      ..beginAuth(serverId, providers: providers);

    final orchestrator = ref.read(authOrchestratorProvider);
    final result = await orchestrator.login(authSystem, serverId);

    switch (result) {
      case LoginAttemptSuccess(:final config, :final user):
        notifier.setAuthenticated(
          serverId: serverId,
          config: config,
          user: user,
        );
      case LoginAttemptRedirect():
        // Web flow: browser redirecting, callback screen will handle it
        // State remains Authenticating until callback completes
        break;
      case LoginAttemptFailure(:final message):
        notifier.setError(message: message, serverId: serverId);
    }
  }

  String? _validateServerUrl(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Server URL is required';
    }
    final trimmed = value.trim();
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      return 'URL must start with http:// or https://';
    }
    final uri = Uri.tryParse(trimmed);
    if (uri == null || uri.host.isEmpty) {
      return 'Invalid URL format';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final appState = ref.watch(appStateProvider);

    // Derive UI state from AppState
    final isProbing = appState is AppStateProbing;
    final isLoggingIn = appState is AppStateAuthenticating;
    final isLoading = isProbing || isLoggingIn;

    final providers = _extractProviders(appState);

    final errorMessage = switch (appState) {
      AppStateError(:final message) => message,
      _ => null,
    };

    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // App title
                  Text(
                    'Soliplex',
                    style: theme.textTheme.headlineMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Connect to a server to get started',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),

                  // Server URL input
                  TextFormField(
                    controller: _serverUrlController,
                    decoration: const InputDecoration(
                      labelText: 'Server URL',
                      hintText: 'https://api.example.com',
                      prefixIcon: Icon(Icons.dns_outlined),
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    enabled: !isLoading,
                    validator: _validateServerUrl,
                    onFieldSubmitted: (_) => _probeServer(),
                  ),
                  const SizedBox(height: 16),

                  // Connect button
                  FilledButton(
                    onPressed: isLoading ? null : _probeServer,
                    child: isProbing
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Connect'),
                  ),

                  // Error message
                  if (errorMessage != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.errorContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.error_outline,
                            color: theme.colorScheme.onErrorContainer,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              errorMessage,
                              style: TextStyle(
                                color: theme.colorScheme.onErrorContainer,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Provider list
                  if (providers.isNotEmpty) ...[
                    const SizedBox(height: 24),
                    const Divider(),
                    const SizedBox(height: 16),
                    Text(
                      'Sign in with',
                      style: theme.textTheme.titleSmall,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    ...providers.map(
                      (provider) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: OutlinedButton.icon(
                          onPressed:
                              isLoggingIn ? null : () => _login(provider),
                          icon: const Icon(Icons.login),
                          label: Text(provider.title),
                        ),
                      ),
                    ),
                    if (isLoggingIn) ...[
                      const SizedBox(height: 8),
                      const LinearProgressIndicator(),
                    ],
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
