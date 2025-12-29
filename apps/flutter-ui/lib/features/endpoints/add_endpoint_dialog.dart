import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/completions_presets.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/saved_endpoint.dart';
import 'package:soliplex/core/services/completions_probe.dart';
import 'package:soliplex/core/services/endpoint_config_service.dart';

/// Dialog for adding or editing an endpoint configuration.
class AddEndpointDialog extends ConsumerStatefulWidget {
  const AddEndpointDialog({super.key, this.existingEndpoint});

  /// Existing endpoint to edit, or null for new endpoint.
  final SavedEndpoint? existingEndpoint;

  /// Show the dialog and return the saved endpoint (or null if cancelled).
  static Future<SavedEndpoint?> show(
    BuildContext context, {
    SavedEndpoint? existingEndpoint,
  }) {
    return showDialog<SavedEndpoint>(
      context: context,
      builder: (context) =>
          AddEndpointDialog(existingEndpoint: existingEndpoint),
    );
  }

  @override
  ConsumerState<AddEndpointDialog> createState() => _AddEndpointDialogState();
}

class _AddEndpointDialogState extends ConsumerState<AddEndpointDialog> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _urlController = TextEditingController();
  final _apiKeyController = TextEditingController();
  final _notesController = TextEditingController();

  bool _isCompletions = true;
  String? _selectedModel;
  List<String> _availableModels = [];
  bool _isProbing = false;
  bool _isSaving = false;
  String? _error;
  CompletionsProviderPreset? _selectedPreset;

  bool get _isEditing => widget.existingEndpoint != null;

  @override
  void initState() {
    super.initState();
    if (_isEditing) {
      final endpoint = widget.existingEndpoint!;
      _nameController.text = endpoint.name;
      _urlController.text = endpoint.url;
      _notesController.text = endpoint.notes ?? '';
      _isCompletions = endpoint.isCompletions;

      if (endpoint.isCompletions) {
        final completions = endpoint.config as CompletionsEndpoint;
        // _selectedModel = completions.defaultModel; // Removed from model
        // _availableModels = completions.availableModels ?? []; // Removed from
        // model
        _selectedModel = completions.model;
        _availableModels = []; // Probe to get available models?
      }

      // Load existing API key
      _loadExistingApiKey();
    }
  }

  Future<void> _loadExistingApiKey() async {
    if (!_isEditing) return;
    final service = ref.read(endpointConfigServiceProvider);
    final apiKey = await service.getApiKey(widget.existingEndpoint!.id);
    if (apiKey != null && mounted) {
      setState(() {
        _apiKeyController.text = apiKey;
      });
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _urlController.dispose();
    _apiKeyController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  void _selectPreset(CompletionsProviderPreset preset) {
    setState(() {
      _selectedPreset = preset;
      _urlController.text = preset.url;
      _nameController.text = preset.name;
      _selectedModel = preset.defaultModel;
      _availableModels = preset.knownModels ?? [];
    });
  }

  Future<void> _probeEndpoint() async {
    if (_urlController.text.trim().isEmpty) {
      setState(() => _error = 'Please enter a URL first');
      return;
    }

    setState(() {
      _isProbing = true;
      _error = null;
    });

    try {
      final probe = ref.read(completionsProbeProvider);
      final result = await probe.probe(
        _urlController.text.trim(),
        apiKey: _apiKeyController.text.isNotEmpty
            ? _apiKeyController.text
            : null,
      );

      setState(() {
        _isProbing = false;
        if (result.isReachable) {
          // Ensure models are unique
          _availableModels = result.availableModels.toSet().toList();

          // If the currently selected model is not in the new list, clear it
          if (_selectedModel != null &&
              !_availableModels.contains(_selectedModel)) {
            _selectedModel = null;
          }

          // Select default if nothing selected
          if (_availableModels.isNotEmpty && _selectedModel == null) {
            _selectedModel = _availableModels.first;
          }

          // Auto-fill name if empty
          if (_nameController.text.isEmpty) {
            final preset = CompletionsProviderPresets.byUrl(
              _urlController.text,
            );
            _nameController.text = preset?.name ?? 'Custom Endpoint';
          }
        } else {
          _error = result.error ?? 'Failed to connect to endpoint';
        }
      });
    } on Object catch (e) {
      setState(() {
        _isProbing = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSaving = true;
      _error = null;
    });

    try {
      final service = ref.read(endpointConfigServiceProvider);

      // Create the endpoint type
      final EndpointConfiguration config;
      if (_isCompletions) {
        config = CompletionsEndpoint(
          url: _urlController.text.trim(),
          label: _nameController.text.trim(),
          model: _selectedModel ?? 'gpt-3.5-turbo',
        );
      } else {
        config = AgUiEndpoint(
          url: _urlController.text.trim(),
          label: _nameController.text.trim(),
        );
      }

      // Create or update the SavedEndpoint
      final SavedEndpoint endpoint;
      if (_isEditing) {
        endpoint = widget.existingEndpoint!.copyWith(
          config: config,
          notes: _notesController.text.isNotEmpty
              ? _notesController.text.trim()
              : null,
        );
      } else {
        endpoint = SavedEndpoint.create(
          config: config,
          notes: _notesController.text.isNotEmpty
              ? _notesController.text.trim()
              : null,
        );
      }

      // Save the config
      await service.saveEndpoint(endpoint);

      // Save API key if provided
      if (_apiKeyController.text.isNotEmpty) {
        await service.saveApiKey(endpoint.id, _apiKeyController.text);
      } else if (_isEditing) {
        // Clear API key if it was removed
        await service.deleteApiKey(endpoint.id);
      }

      // Refresh the endpoints list
      ref.invalidate(endpointConfigsProvider);

      if (mounted) {
        Navigator.of(context).pop(endpoint);
      }
    } on Object catch (e) {
      setState(() {
        _isSaving = false;
        _error = e.toString();
      });
    }
  }

  String? _validateName(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Please enter a name';
    }
    return null;
  }

  String? _validateUrl(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Please enter a URL';
    }
    final uri = Uri.tryParse(value.trim());
    if (uri == null || !uri.hasScheme) {
      return 'Please enter a valid URL';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return AlertDialog(
      title: Text(_isEditing ? 'Edit Endpoint' : 'Add Endpoint'),
      content: SizedBox(
        width: 500,
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Endpoint type selector
                if (!_isEditing) ...[
                  Text('Endpoint Type', style: theme.textTheme.titleSmall),
                  const SizedBox(height: 8),
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(
                        value: true,
                        label: Text('Completions API'),
                        icon: Icon(Icons.chat),
                      ),
                      ButtonSegment(
                        value: false,
                        label: Text('AG-UI Server'),
                        icon: Icon(Icons.smart_toy),
                      ),
                    ],
                    selected: {_isCompletions},
                    onSelectionChanged: (selected) {
                      setState(() => _isCompletions = selected.first);
                    },
                  ),
                  const SizedBox(height: 24),
                ],

                // Provider presets (for completions)
                if (_isCompletions && !_isEditing) ...[
                  Text('Quick Setup', style: theme.textTheme.titleSmall),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: CompletionsProviderPresets.all.map((preset) {
                      final isSelected = _selectedPreset?.id == preset.id;
                      return FilterChip(
                        selected: isSelected,
                        label: Text(preset.name),
                        avatar: Icon(preset.icon, size: 18),
                        onSelected: (_) => _selectPreset(preset),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 24),
                ],

                // Name field
                TextFormField(
                  controller: _nameController,
                  validator: _validateName,
                  decoration: const InputDecoration(
                    labelText: 'Name',
                    hintText: 'My OpenAI Endpoint',
                    prefixIcon: Icon(Icons.label),
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),

                // URL field with probe button
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _urlController,
                        validator: _validateUrl,
                        decoration: const InputDecoration(
                          labelText: 'URL',
                          hintText: 'https://api.openai.com',
                          prefixIcon: Icon(Icons.link),
                          border: OutlineInputBorder(),
                        ),
                        keyboardType: TextInputType.url,
                      ),
                    ),
                    if (_isCompletions) ...[
                      const SizedBox(width: 8),
                      SizedBox(
                        height: 56,
                        child: FilledButton.tonal(
                          onPressed: _isProbing ? null : _probeEndpoint,
                          child: _isProbing
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Text('Test'),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 16),

                // API Key field (for completions)
                if (_isCompletions) ...[
                  TextFormField(
                    controller: _apiKeyController,
                    decoration: const InputDecoration(
                      labelText: 'API Key (optional)',
                      hintText: 'sk-...',
                      prefixIcon: Icon(Icons.key),
                      border: OutlineInputBorder(),
                    ),
                    obscureText: true,
                  ),
                  const SizedBox(height: 16),
                ],

                // Model selector
                if (_isCompletions && _availableModels.isNotEmpty) ...[
                  DropdownButtonFormField<String>(
                    initialValue: _selectedModel,
                    decoration: const InputDecoration(
                      labelText: 'Default Model',
                      prefixIcon: Icon(Icons.psychology),
                      border: OutlineInputBorder(),
                    ),
                    items: _availableModels
                        .map(
                          (model) => DropdownMenuItem(
                            value: model,
                            child: Text(model),
                          ),
                        )
                        .toList(),
                    onChanged: (newValue) {
                      setState(() => _selectedModel = newValue);
                    },
                  ),
                  const SizedBox(height: 16),
                ],

                // Notes field
                TextFormField(
                  controller: _notesController,
                  decoration: const InputDecoration(
                    labelText: 'Notes (optional)',
                    hintText: 'Personal account, rate limited...',
                    prefixIcon: Icon(Icons.notes),
                    border: OutlineInputBorder(),
                  ),
                  maxLines: 2,
                ),

                // Error display
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: colorScheme.errorContainer,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.error_outline,
                          color: colorScheme.onErrorContainer,
                          size: 20,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _error!,
                            style: TextStyle(
                              color: colorScheme.onErrorContainer,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _isSaving ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _isSaving ? null : _save,
          child: _isSaving
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(_isEditing ? 'Save' : 'Add'),
        ),
      ],
    );
  }
}
