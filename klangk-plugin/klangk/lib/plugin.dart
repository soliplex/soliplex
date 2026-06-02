import 'package:flutter/material.dart';
import 'package:klangk_plugin_api/klangk_plugin_api.dart';
import 'soliplex_tools.dart';

class SoliplexPlugin extends ToolPlugin with ChangeNotifier {
  bool _authenticated = hasValidToken();
  bool _loggingIn = false;

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

  Future<void> login() async {
    _loggingIn = true;
    notifyListeners();
    try {
      await popupLogin();
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

  @override
  Widget build(BuildContext context) {
    if (widget.plugin.authenticated) {
      return const SizedBox.shrink();
    }
    return Positioned(
      top: 8,
      right: 8,
      child: Material(
        elevation: 4,
        borderRadius: BorderRadius.circular(8),
        color: Theme.of(context).colorScheme.errorContainer,
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: widget.plugin.loggingIn ? null : () {
            widget.plugin.login();
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(
                horizontal: 12, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.plugin.loggingIn)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 2),
                  )
                else
                  Icon(Icons.link,
                      size: 16,
                      color: Theme.of(context)
                          .colorScheme
                          .onErrorContainer),
                const SizedBox(width: 6),
                Text(
                  widget.plugin.loggingIn
                      ? 'Connecting...'
                      : 'Connect to Soliplex',
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context)
                        .colorScheme
                        .onErrorContainer,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
