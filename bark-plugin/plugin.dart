import 'package:bark_frontend/tools/tool_plugin.dart';
import 'soliplex_tools.dart';

class SoliplexPlugin extends ToolPlugin {
  @override
  Map<String, ToolHandler> get handlers => {
        'soliplex_list_rooms': _listRooms,
        'soliplex_query': _query,
      };

  Future<String> _listRooms(Map<String, dynamic> request) async {
    try {
      final client = SoliplexClient();
      final rooms = await client.listRooms();
      if (rooms.isEmpty) return 'No rooms available.';
      return rooms
          .map((r) =>
              '- ${r['room_id'] ?? r['id']}: ${r['name'] ?? 'unnamed'} — ${r['description'] ?? 'no description'}')
          .join('\n');
    } catch (e) {
      return 'Error listing rooms: $e';
    }
  }

  Future<String> _query(Map<String, dynamic> request) async {
    final roomId = request['room_id'] as String? ?? 'search';
    final question = request['question'] as String? ?? '';
    if (question.isEmpty) return 'Error: question is required';
    try {
      final client = SoliplexClient();
      return await client.queryRoom(roomId, question);
    } catch (e) {
      return 'Error querying Soliplex: $e';
    }
  }
}
