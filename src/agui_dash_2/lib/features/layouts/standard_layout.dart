import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../chat/chat_content.dart';

/// Standard layout - full-screen chat.
///
/// This is the default layout mode, displaying just the chat widget.
class StandardLayout extends ConsumerWidget {
  final String? roomId;

  const StandardLayout({super.key, this.roomId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ChatContent(roomId: roomId);
  }
}
