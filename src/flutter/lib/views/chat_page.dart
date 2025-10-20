import 'dart:convert';

import 'package:flutter/material.dart';

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/views/map_page.dart';

class ChatPage extends ConsumerWidget {
  const ChatPage({required this.llmProvider, this.style, super.key});

  final LlmProvider llmProvider;
  final LlmChatViewStyle? style;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentChatroomConfig = ref
        .read(currentChatroomControllerProvider.notifier)
        .currentChatPageConfig
        .roomConfig;

    return Column(
      children: [
        Expanded(
          child: LlmChatView(
            provider: llmProvider,
            style: style,
            welcomeMessage: currentChatroomConfig.welcomeMessage,
            suggestions: currentChatroomConfig.suggestions ?? [],
            enableAttachments: currentChatroomConfig.enableAttachments ?? false,
            enableVoiceNotes: false,
            mapBuilder: _mapBuilder,
            onErrorCallback: (context, error) async {
              await showDialog(
                context: context,
                barrierDismissible: false,
                builder: (context) => Builder(
                  builder: (context) {
                    return AlertDialog(
                      content: SingleChildScrollView(
                        child: Text(error.toString()),
                      ),
                      actions: [
                        TextButton(
                          onPressed: () {
                            GoRouter.of(context).go('/');
                            Navigator.pop(context);
                          },
                          child: const Text('Back'),
                        ),
                        TextButton(
                          onPressed: () {
                            Navigator.pop(context);
                          },
                          child: const Text('OK'),
                        ),
                      ],
                    );
                  },
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _mapBuilder(context, response) {
    final jsonResponse = jsonDecode(response);

    final positions = <Position>[];
    for (final coordinate in jsonResponse['coords'] ?? []) {
      positions.add(
        Position(
          latitude: double.tryParse('${coordinate['lat']}') ?? 0.0,
          longitude: double.tryParse('${coordinate['lng']}') ?? 0.0,
          timestamp: int.tryParse('${coordinate['time']}') == null
              ? DateTime.now()
              : DateTime.fromMillisecondsSinceEpoch(
                  int.parse('${coordinate['time']}'),
                ),
          accuracy: double.tryParse('${coordinate['acc']}') ?? 0.0,
          altitude: double.tryParse('${coordinate['alt']}') ?? 0.0,
          altitudeAccuracy: double.tryParse('${coordinate['alt-acc']}') ?? 0,
          heading: double.tryParse('${coordinate['head']}') ?? 0.0,
          headingAccuracy: double.tryParse('${coordinate['head-acc']}') ?? 0.0,
          speed: double.tryParse('${coordinate['speed']}') ?? 0.0,
          speedAccuracy: double.tryParse('${coordinate['speed-acc']}') ?? 0.0,
        ),
      );
    }

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        const double percentage = 0.5;
        final double maxHeight =
            MediaQuery.of(context).size.height * percentage;
        final double maxWidth = MediaQuery.of(context).size.width * percentage;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  flex: 4,
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final position in positions) ...<Widget>[
                          PositionMetadata(position),
                        ],
                      ],
                    ),
                  ),
                ),
                Expanded(
                  flex: 1,
                  child: Align(
                    alignment: Alignment.centerRight,
                    child: IconButton(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute<Widget>(
                            builder: (_) {
                              return Scaffold(
                                appBar: AppBar(
                                  leading: IconButton(
                                    onPressed: () => Navigator.pop(context),
                                    icon: const Icon(Icons.arrow_back),
                                  ),
                                ),
                                body: MapPage(positions),
                                extendBody: true,
                              );
                            },
                          ),
                        );
                      },
                      icon: Icon(Icons.fullscreen),
                    ),
                  ),
                ),
              ],
            ),
            SizedBox(
              width: maxWidth,
              height: maxHeight,
              child: MapPage(positions),
            ),
          ],
        );
      },
    );
  }
}

class PositionMetadata extends StatelessWidget {
  const PositionMetadata(this.position, {super.key});
  final Position position;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text('lat: ', style: TextStyle(fontWeight: FontWeight.bold)),
        Text('${position.latitude}'),
        SizedBox(width: 12),
        Text('lng: ', style: TextStyle(fontWeight: FontWeight.bold)),
        Text('${position.longitude}'),
      ],
    );
  }
}
