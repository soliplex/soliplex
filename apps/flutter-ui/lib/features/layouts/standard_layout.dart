import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/features/chat/chat_content.dart';

/// Standard layout - full-screen chat.
///
/// This is the default layout mode, displaying just the chat widget.
class StandardLayout extends ConsumerWidget {
  const StandardLayout({super.key, this.roomId});
  final String? roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ChatContent(roomId: roomId);
  }
}
