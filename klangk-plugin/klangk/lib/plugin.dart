import 'dart:js_interop';
import 'package:flutter/material.dart';
import 'package:klangk_plugin_api/klangk_plugin_api.dart';
import 'package:web/web.dart' as web;
import 'soliplex_tools.dart';

const soliplexPluginVersion = '2026-06-02b';

class SoliplexPlugin extends ToolPlugin with ChangeNotifier {
  bool _authenticated = hasValidToken();
  bool _loggingIn = false;

  SoliplexPlugin() {
    web.window.localStorage.setItem(
        'soliplex_plugin_version', soliplexPluginVersion);
    // Register a global JS function for easy console debugging.
    _registerJsHelpers();
  }

  static void _registerJsHelpers() {
    (web.window as JSObject).setProperty(
      'soliplexClearTokens'.toJS,
      (() {
        clearStoredTokens();
        web.window.console.log('Soliplex tokens cleared.'.toJS);
      }).toJS,
    );
    (web.window as JSObject).setProperty(
      'soliplexVersion'.toJS,
      (() {
        web.window.console.log(
            'Soliplex plugin version: $soliplexPluginVersion'.toJS);
        return soliplexPluginVersion.toJS;
      }).toJS,
    );
  }

  bool get authenticated => _authenticated;
  bool get loggingIn => _loggingIn;

  @override
  Map<String, ToolHandler> get handlers => {
        'soliplex_list_rooms': _listRooms,
        'soliplex_query': _query,
      };

  @override
  Widget? buildOverlay(BuildContext context) {
    return _SoliplexAuthOverlay(plugin: this);
  }

  Future<void> login(String systemId) async {
    _loggingIn = true;
    notifyListeners();
    try {
      await popupLogin(systemId);
      _authenticated = true;
    } catch (_) {
      _authenticated = false;
    } finally {
      _loggingIn = false;
      notifyListeners();
    }
  }

  Future<String> _listRooms(Map<String, dynamic> request) async {
    try {
      final client = SoliplexClient();
      final rooms = await client.listRooms();
      _authenticated = hasValidToken();
      notifyListeners();
      if (rooms.isEmpty) return 'No rooms available.';
      return rooms
          .map((r) =>
              '- ${r['room_id'] ?? r['id']}: ${r['name'] ?? 'unnamed'}'
              ' — ${r['description'] ?? 'no description'}')
          .join('\n');
    } catch (e) {
      _authenticated = hasValidToken();
      notifyListeners();
      return 'Error listing rooms: $e';
    }
  }

  Future<String> _query(Map<String, dynamic> request) async {
    final roomId = request['room_id'] as String? ?? 'search';
    final question = request['question'] as String? ?? '';
    if (question.isEmpty) return 'Error: question is required';
    try {
      final client = SoliplexClient();
      final result = await client.queryRoom(roomId, question);
      _authenticated = hasValidToken();
      notifyListeners();
      return result;
    } catch (e) {
      _authenticated = hasValidToken();
      notifyListeners();
      return 'Error querying Soliplex: $e';
    }
  }
}

class _SoliplexAuthOverlay extends StatefulWidget {
  final SoliplexPlugin plugin;
  const _SoliplexAuthOverlay({required this.plugin});

  @override
  State<_SoliplexAuthOverlay> createState() =>
      _SoliplexAuthOverlayState();
}

class _SoliplexAuthOverlayState extends State<_SoliplexAuthOverlay> {
  Map<String, dynamic>? _authSystems;
  bool _loadingSystems = false;
  bool _expanded = false;
  String? _selectedSystem;

  @override
  void initState() {
    super.initState();
    widget.plugin.addListener(_onUpdate);
  }

  @override
  void dispose() {
    widget.plugin.removeListener(_onUpdate);
    super.dispose();
  }

  void _onUpdate() {
    if (mounted) setState(() {});
  }

  Future<void> _expand() async {
    debugPrint('soliplex: _expand called, '
        'authenticated=${widget.plugin.authenticated}, '
        'mounted=$mounted');
    if (_authSystems == null && !_loadingSystems) {
      _loadingSystems = true;
      setState(() {});
      try {
        _authSystems = await getAuthSystems();
        debugPrint('soliplex: got auth systems: '
            '${_authSystems?.keys.toList()}');
        // Pre-select the first system.
        if (_authSystems!.isNotEmpty) {
          _selectedSystem = _authSystems!.keys.first;
        }
      } catch (e) {
        debugPrint('soliplex: getAuthSystems failed: $e');
        // Leave _authSystems null; user can retry.
      } finally {
        _loadingSystems = false;
      }
    }
    _expanded = true;
    debugPrint('soliplex: setting expanded=true, '
        'authenticated=${widget.plugin.authenticated}, '
        'mounted=$mounted');
    if (mounted) setState(() {});
  }

  void _connect() {
    if (_selectedSystem == null) return;
    widget.plugin.login(_selectedSystem!);
  }

  @override
  Widget build(BuildContext context) {
    debugPrint('soliplex: build called, '
        'authenticated=${widget.plugin.authenticated}, '
        'expanded=$_expanded');
    if (widget.plugin.authenticated) {
      return const SizedBox.shrink();
    }

    final errorContainer =
        Theme.of(context).colorScheme.errorContainer;
    final onErrorContainer =
        Theme.of(context).colorScheme.onErrorContainer;

    // Collapsed state: just the button.
    if (!_expanded) {
      return Positioned(
        top: 8,
        right: 8,
        child: Material(
          elevation: 4,
          borderRadius: BorderRadius.circular(8),
          color: errorContainer,
          child: InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: _expand,
            child: Padding(
              padding: const EdgeInsets.symmetric(
                  horizontal: 12, vertical: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.link,
                      size: 16, color: onErrorContainer),
                  const SizedBox(width: 6),
                  Text(
                    'Connect to Soliplex',
                    style: TextStyle(
                        fontSize: 12, color: onErrorContainer),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    // Expanded state: radio buttons + connect button.
    return Positioned(
      top: 8,
      right: 8,
      child: Material(
        elevation: 4,
        borderRadius: BorderRadius.circular(8),
        color: errorContainer,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.link,
                      size: 16, color: onErrorContainer),
                  const SizedBox(width: 6),
                  Text(
                    'Connect to Soliplex',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: onErrorContainer,
                    ),
                  ),
                  const SizedBox(width: 8),
                  InkWell(
                    onTap: () => setState(() => _expanded = false),
                    child: Icon(Icons.close,
                        size: 14, color: onErrorContainer),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              if (_loadingSystems)
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else if (_authSystems == null)
                Text('Failed to load providers',
                    style: TextStyle(
                        fontSize: 11, color: onErrorContainer))
              else
                ..._authSystems!.entries.map((entry) {
                  final systemData =
                      entry.value as Map<String, dynamic>;
                  final title =
                      systemData['title'] as String? ?? entry.key;
                  return InkWell(
                    onTap: widget.plugin.loggingIn
                        ? null
                        : () =>
                            setState(() => _selectedSystem = entry.key),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Radio<String>(
                          value: entry.key,
                          groupValue: _selectedSystem,
                          onChanged: widget.plugin.loggingIn
                              ? null
                              : (v) =>
                                  setState(() => _selectedSystem = v),
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                          visualDensity: VisualDensity.compact,
                        ),
                        Text(title,
                            style: TextStyle(
                                fontSize: 12,
                                color: onErrorContainer)),
                      ],
                    ),
                  );
                }),
              const SizedBox(height: 4),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: (widget.plugin.loggingIn ||
                          _selectedSystem == null)
                      ? null
                      : _connect,
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 6),
                    textStyle: const TextStyle(fontSize: 12),
                  ),
                  child: widget.plugin.loggingIn
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                              strokeWidth: 2),
                        )
                      : const Text('Connect'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
