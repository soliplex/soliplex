import 'package:flutter/material.dart';
import '../../keyboard/keyboard_shortcuts_help_dialog.dart';
import 'room_list.dart';
import 'server_selector.dart';

class AppNavigationContent extends StatelessWidget {
  const AppNavigationContent({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const ServerSelector(),
        const Expanded(child: RoomList()),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.help_outline),
          title: const Text('Help'),
          onTap: () {
            KeyboardShortcutsHelpDialog.show(context);
          },
        ),
      ],
    );
  }
}

class AppNavigationDrawer extends StatelessWidget {
  const AppNavigationDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    return const Drawer(
      child: AppNavigationContent(),
    );
  }
}