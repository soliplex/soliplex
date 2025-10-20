import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/views/chatroom_info_view.dart';
import 'package:soliplex_client/views/status_view.dart';

class SoliplexAppBar extends ConsumerStatefulWidget
    implements PreferredSizeWidget {
  const SoliplexAppBar({super.key});

  @override
  ConsumerState<SoliplexAppBar> createState() => _SoliplexAppBarState();

  @override
  Size get preferredSize => Size.fromHeight(kToolbarHeight);
}

class _SoliplexAppBarState extends ConsumerState<SoliplexAppBar> {
  @override
  Widget build(BuildContext context) {
    final appState = ref.watch(appStateController);

    return AppBar(
      leading: SizedBox.square(
        dimension: 48.0,
        child: InkWell(
          onTap: appState.canNavigate
              ? () async {
                  if (context.mounted) {
                    context.go('/chat');
                  }
                }
              : null,
          child: Icon(Icons.home),
        ),
      ),
      title: InkWell(
        onTap: () async => appState.canNavigate
            ? await showDialog(
                context: context,
                builder: (context) => ChatroomInfoView(
                  roomId: ref
                      .read(currentChatroomControllerProvider.notifier)
                      .currentChatPageConfig
                      .roomConfig
                      .roomId,
                ),
              )
            : null,
        child: Text(appState.title),
      ),
      actionsPadding: EdgeInsets.only(right: 24.0),
      actions: appState.title == 'Soliplex Client'
          ? null
          : [
              DropdownButton<AppBarAction>(
                items: [
                  DropdownMenuItem(
                    value: AppBarAction.status,
                    child: Text('Status'),
                  ),
                  DropdownMenuItem(
                    value: AppBarAction.logout,
                    child: Text('Logout'),
                  ),
                ],
                onChanged: (AppBarAction? newValue) async {
                  switch (newValue) {
                    case AppBarAction.logout:
                      final logout = await _logoutConfirmation();

                      if (logout ?? false) {
                        final config = await ref
                            .read(oidcAuthController)
                            .oidcAuthInteractor
                            .getSsoConfig();

                        if (config == null) {
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text('No user logged in')),
                            );
                          }
                          return;
                        }
                        try {
                          await ref
                              .read(oidcAuthController)
                              .oidcAuthInteractor
                              .logout(config);
                          ref
                                  .read(oidcAuthController)
                                  .oidcAuthInteractor
                                  .useAuth =
                              false;
                          if (context.mounted) {
                            context.go('/');
                          }
                        } catch (exception) {
                          await _showLogOutErrorMessage('$exception');
                        }
                      }
                    case AppBarAction.status:
                      await showDialog(
                        context: context,
                        builder: (context) =>
                            AlertDialog(content: StatusView()),
                      );
                    case null:
                  }
                },
                underline: Container(
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.transparent),
                  ),
                ),
                icon: Icon(Icons.menu),
              ),
            ],
    );
  }

  Future<bool?> _logoutConfirmation() => showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      content: Text('Are you sure you want to logout?'),
      actions: [
        ElevatedButton(
          onPressed: () {
            context.pop(true);
          },
          child: Text('Yes'),
        ),
        ElevatedButton(onPressed: () => context.pop(false), child: Text('No')),
      ],
    ),
  );

  Future<void> _showLogOutErrorMessage(String exception) => showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('Error occurred while logging out.'),
      content: SingleChildScrollView(child: Text(exception)),
      actions: [
        ElevatedButton(
          onPressed: () {
            context.pop();
          },
          child: Text('Ok'),
        ),
      ],
    ),
  );
}

enum AppBarAction { status, logout }
