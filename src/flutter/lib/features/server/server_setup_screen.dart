import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/utils/api_constants.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/features/server/oidc_provider_selector.dart';
import 'package:soliplex/features/server/server_history_widget.dart';

/// First-run screen for server configuration.
///
/// Shows:
/// - URL input field with validation
/// - Connect button
/// - Server history (if any)
/// - OIDC provider selection (when needed)
class ServerSetupScreen extends ConsumerStatefulWidget {
  const ServerSetupScreen({super.key, this.onConnected});
  final VoidCallback? onConnected;

  @override
  ConsumerState<ServerSetupScreen> createState() => _ServerSetupScreenState();
}

class _ServerSetupScreenState extends ConsumerState<ServerSetupScreen> {
  final _urlController = TextEditingController(
    text: ApiConstants.defaultServerUrl,
  );
  final _formKey = GlobalKey<FormState>();

  bool _isProbing = false;
  bool _isSelectingFromHistory = false;
  ServerInfo? _serverInfo;
  String? _error;

  @override
  void initState() {
    super.initState();
    // Check if we're in NeedsAuth state - show providers from app state
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkAppState();
    });
  }

  void _checkAppState() {
    final appState = ref.read(currentAppStateProvider);
    if (appState is AppStateNeedsAuth) {
      // Pre-populate the URL from the saved server
      _urlController.text = appState.server.url;
      setState(() {
        _serverInfo = ServerInfo(
          url: appState.server.url,
          isReachable: true,
          oidcProviders: appState.providers,
        );
      });
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _probeServer() async {
    // Guard against concurrent operations (e.g., history selection in progress)
    if (_isSelectingFromHistory) return;
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isProbing = true;
      _error = null;
      _serverInfo = null;
    });

    try {
      final serverRegistry = ref.read(serverRegistryProvider);
      final info = await serverRegistry.probeServer(_urlController.text);

      setState(() {
        _serverInfo = info;
        _isProbing = false;
      });

      if (!info.isReachable) {
        setState(() {
          _error = info.error ?? 'Server unreachable';
        });
        return;
      }

      // Set server via AppStateManager - it handles auth state transitions
      final appStateManager = ref.read(appStateManagerProvider);
      await appStateManager.setServer(info);

      // If server doesn't require auth, call onConnected to pop this screen
      // (for auth servers, OIDCProviderSelector handles the callback)
      if (!info.requiresAuth) {
        widget.onConnected?.call();
      }
    } on Object catch (e) {
      setState(() {
        _isProbing = false;
        _error = e.toString();
      });
    }
  }

  String? _validateUrl(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Please enter a server URL';
    }

    // Basic URL validation
    final trimmed = value.trim();
    if (!trimmed.contains('.') && !trimmed.contains('localhost')) {
      return 'Please enter a valid URL';
    }

    return null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final serverHistory = ref.watch(serverHistoryProvider);
    final appState = ref.watch(currentAppStateProvider);

    // Get OIDC providers from app state if in NeedsAuth state
    final List<OIDCAuthSystem> oidcProviders;
    final String? serverUrl;
    if (appState is AppStateNeedsAuth) {
      oidcProviders = appState.providers;
      serverUrl = appState.server.url;
    } else if (_serverInfo != null && _serverInfo!.requiresAuth) {
      oidcProviders = _serverInfo!.oidcProviders;
      serverUrl = _serverInfo!.url;
    } else {
      oidcProviders = [];
      serverUrl = null;
    }

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Icon(
                Icons.dns_outlined,
                size: 64,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(height: 16),
              Text(
                'Connect to Server',
                style: theme.textTheme.headlineMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Enter the URL of your Soliplex server',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),

              // URL Input Form
              Form(
                key: _formKey,
                child: TextFormField(
                  controller: _urlController,
                  validator: _validateUrl,
                  decoration: InputDecoration(
                    labelText: 'Server URL',
                    hintText: ApiConstants.defaultServerUrl,
                    prefixIcon: const Icon(Icons.link),
                    border: const OutlineInputBorder(),
                    suffixIcon: _isProbing
                        ? const Padding(
                            padding: EdgeInsets.all(12),
                            child: SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          )
                        : null,
                  ),
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.go,
                  onFieldSubmitted: (_) => _probeServer(),
                  enabled: !_isProbing,
                ),
              ),
              const SizedBox(height: 16),

              // Error message
              if (_error != null) ...[
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
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _error!,
                          style: TextStyle(
                            color: theme.colorScheme.onErrorContainer,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // Connect button
              FilledButton.icon(
                onPressed: _isProbing ? null : _probeServer,
                icon: const Icon(Icons.login),
                label: const Text('Connect'),
              ),

              // OIDC Provider Selection
              if (oidcProviders.isNotEmpty && serverUrl != null) ...[
                const SizedBox(height: 24),
                const Divider(),
                const SizedBox(height: 16),
                Text(
                  'Choose login method',
                  style: theme.textTheme.titleMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                OIDCProviderSelector(
                  providers: oidcProviders,
                  serverUrl: serverUrl,
                  onAuthenticated: () {
                    widget.onConnected?.call();
                  },
                ),
              ],

              // Server History
              if (serverHistory.isNotEmpty) ...[
                const SizedBox(height: 32),
                const Divider(),
                const SizedBox(height: 16),
                Text('Recent Servers', style: theme.textTheme.titleMedium),
                const SizedBox(height: 8),
                ServerHistoryWidget(
                  onServerSelected: (server) async {
                    DebugLog.ui('Server selected from history: ${server.url}');
                    // Guard against duplicate calls
                    if (_isSelectingFromHistory) return;

                    // Set flag to prevent _probeServer and duplicate selections
                    setState(() => _isSelectingFromHistory = true);

                    // Update the text field to show what's happening
                    _urlController.text = server.url;

                    // Unfocus any text fields to prevent form submission side
                    // effects
                    FocusScope.of(context).unfocus();

                    try {
                      // Use selectServerFromHistory which handles proper state
                      // transitions
                      // instead of probing which creates a new server entry
                      final appStateManager = ref.read(appStateManagerProvider);
                      await appStateManager.selectServerFromHistory(server.id);
                      // onConnected callback will be triggered by the state
                      // change
                      // if the server doesn't need auth
                      if (!mounted) return;
                      final newState = ref.read(currentAppStateProvider);
                      if (newState is AppStateReady) {
                        widget.onConnected?.call();
                      }
                    } finally {
                      if (mounted) {
                        setState(() => _isSelectingFromHistory = false);
                      }
                    }
                  },
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
