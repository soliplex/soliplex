import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/services/server_config_service.dart';
import 'server_history_widget.dart';
import 'oidc_provider_selector.dart';

/// First-run screen for server configuration.
///
/// Shows:
/// - URL input field with validation
/// - Connect button
/// - Server history (if any)
/// - OIDC provider selection (when needed)
class ServerSetupScreen extends ConsumerStatefulWidget {
  final VoidCallback? onConnected;

  const ServerSetupScreen({
    super.key,
    this.onConnected,
  });

  @override
  ConsumerState<ServerSetupScreen> createState() => _ServerSetupScreenState();
}

class _ServerSetupScreenState extends ConsumerState<ServerSetupScreen> {
  final _urlController = TextEditingController(text: 'http://localhost:8000');
  final _formKey = GlobalKey<FormState>();

  bool _isProbing = false;
  ServerInfo? _serverInfo;
  String? _error;

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _probeServer() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isProbing = true;
      _error = null;
      _serverInfo = null;
    });

    try {
      final serverConfig = ref.read(serverConfigProvider);
      final info = await serverConfig.probeServer(_urlController.text);

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

      // Register the server with serverConfig (needed for AuthService)
      await serverConfig.connectToServer(info);

      // If server doesn't require auth, navigate immediately
      if (info.isOpenAccess) {
        widget.onConnected?.call();
      }
      // Otherwise, show OIDC provider selection (server is already registered)
    } catch (e) {
      setState(() {
        _isProbing = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _connectToServer(ServerInfo info) async {
    try {
      final serverConfig = ref.read(serverConfigProvider);
      await serverConfig.connectToServer(info);
      widget.onConnected?.call();
    } catch (e) {
      setState(() {
        _error = 'Failed to connect: $e';
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

    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
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
                      hintText: 'http://localhost:8000',
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
                if (_serverInfo != null && _serverInfo!.requiresAuth) ...[
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
                    providers: _serverInfo!.oidcProviders,
                    serverUrl: _serverInfo!.url,
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
                  Text(
                    'Recent Servers',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  ServerHistoryWidget(
                    onServerSelected: (server) {
                      _urlController.text = server.url;
                      _probeServer();
                    },
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
