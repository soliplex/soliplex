import 'package:flutter/material.dart';
import 'package:soliplex/features/keyboard/keyboard_shortcuts_help_dialog.dart';
import 'package:soliplex/features/navigation/widgets/room_list.dart';
import 'package:soliplex/features/navigation/widgets/server_selector.dart';

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
            KeyboardShortcutsHelpDialog.show(context: context);
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
    return const Drawer(child: AppNavigationContent());
  }
}
