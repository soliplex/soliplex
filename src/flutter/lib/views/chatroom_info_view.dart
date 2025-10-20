import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';

class ChatroomInfoView extends ConsumerWidget {
  const ChatroomInfoView({required this.roomId, super.key});

  final String roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.arrow_back),
        ),
        title: Text('Room Config'),
      ),
      body: SafeArea(
        child: FutureBuilder(
          future: chatroomController.retrieveChatroomInformation(
            roomId: roomId,
          ),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return CircularProgressIndicator(); // Show loading indicator
            } else if (snapshot.hasError) {
              final errorText = 'Error: ${snapshot.error}';
              debugPrint(errorText);
              return Text(errorText); // Show error
            } else if (snapshot.hasData) {
              final chatroomInfo = snapshot.data!;
              final String? mcpToken = chatroomInfo.remove('mcp_token');

              return SingleChildScrollView(
                child: Column(
                  children: [
                    Divider(color: Colors.grey.withAlpha(150)),
                    ChatroomInformationDisplay(json: chatroomInfo),
                    if (chatroomInfo['allow_mcp'] ?? false)
                      McpTokenButton(roomId, mcpToken),
                  ],
                ),
              );
            } else {
              return Text('Could not fetch chatroom information');
            }
          },
        ),
      ),
      extendBody: true,
    );
  }
}

class ChatroomInformationDisplay extends StatelessWidget {
  const ChatroomInformationDisplay({required this.json, super.key});

  final Map<String, dynamic> json;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: json.entries.map((entry) {
        return _buildJsonEntry(entry.key, entry.value);
      }).toList(),
    );
  }

  bool tileInitiallyExpanded(dynamic value) {
    return !((value is Map) ||
        (value is String && value.length > 300) ||
        (value is List && value.length > 1));
  }

  Widget _buildJsonEntry(String key, dynamic value) {
    final tileBackgroundColor = const Color.fromARGB(255, 128, 156, 170);

    final startExpanded = tileInitiallyExpanded(value);

    return ExpansionTile(
      title: Container(
        padding: EdgeInsets.all(4.0),
        decoration: BoxDecoration(
          color: !startExpanded || (value is Map || value is Iterable)
              ? tileBackgroundColor.withAlpha(60)
              : tileBackgroundColor.withAlpha(15),
          borderRadius: BorderRadius.circular(6.0),
        ),
        child: Text(
          key,
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
      ),
      showTrailingIcon: !startExpanded || (value is Map || value is Iterable)
          ? true
          : false,
      initiallyExpanded: startExpanded,
      expandedAlignment: Alignment.centerLeft,
      shape: BoxBorder.fromLTRB(
        bottom: BorderSide(color: Colors.grey.withAlpha(100)),
      ),
      childrenPadding: EdgeInsets.only(bottom: 8.0),
      children: [_buildValueWidget(value)],
    );
  }

  Widget _buildValueWidget(dynamic value) {
    if (value is Map) {
      return value.isEmpty
          ? _buildValueWidget('Field Not Used')
          : Column(
              children: value.entries.map((nestedEntry) {
                return Container(
                  margin: EdgeInsets.only(left: 16.0),
                  child: _buildJsonEntry(nestedEntry.key, nestedEntry.value),
                );
              }).toList(),
            );
    } else if (value is List) {
      return value.isEmpty
          ? _buildValueWidget('Field Not Used')
          : Column(
              children: List.generate(value.length, (index) {
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16.0),
                  child: Text('Item $index: ${value[index]}'),
                );
              }),
            );
    } else {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16.0),
        child: SelectableText('$value'),
      );
    }
  }
}

class McpTokenButton extends StatelessWidget {
  const McpTokenButton(this.roomId, this.mcpToken, {super.key});

  final String roomId;
  final String? mcpToken;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: () async {
        try {
          if (context.mounted) {
            await showDialog(
              context: context,
              builder: (context) => SafeArea(
                child: AlertDialog(
                  title: Text('MCP Token'),
                  content: SingleChildScrollView(
                    child: Column(
                      children: [
                        (mcpToken == null || mcpToken!.isEmpty)
                            ? Text('No MCP Token Provided')
                            : SelectableText(mcpToken!),
                        if (mcpToken != null)
                          IconButton(
                            onPressed: () async {
                              _copyToClipboard(mcpToken!, context);
                              context.pop();
                            },
                            color: Colors.black.withAlpha(120),
                            iconSize: 16.0,
                            icon: Icon(Icons.copy),
                          ),
                      ],
                    ),
                  ),
                  actions: [
                    ElevatedButton(
                      onPressed: () => context.pop(),
                      child: Text('OK'),
                    ),
                  ],
                ),
              ),
            );
          } else if (context.mounted) {
            _displayTokenMCPErrorMessage(context);
          }
        } catch (e) {
          if (context.mounted) {
            _displayTokenMCPErrorMessage(context);
          }
        }
      },
      child: Text('MCP Token'),
    );
  }

  void _copyToClipboard(String text, BuildContext context) {
    Clipboard.setData(ClipboardData(text: text))
        .then((_) {
          if (context.mounted) {
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(SnackBar(content: Text('Copied to clipboard!')));
          }
        })
        .catchError((error) {
          if (context.mounted) {
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(SnackBar(content: Text('Failed to copy: $error')));
          }
        });
  }

  void _displayTokenMCPErrorMessage(BuildContext context) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('No MCP Token for `$roomId`')));
  }
}
