import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/features/navigation/widgets/navigation_drawer.dart';

class AppScaffold extends ConsumerWidget {
  const AppScaffold({required this.child, super.key});
  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Simple responsive check
    final isDesktop = MediaQuery.of(context).size.width > 800;

    return Scaffold(
      drawer: isDesktop ? null : const AppNavigationDrawer(),
      body: Row(
        children: [
          if (isDesktop)
            Container(
              width: 300,
              decoration: BoxDecoration(
                border: Border(
                  right: BorderSide(color: Theme.of(context).dividerColor),
                ),
              ),
              child: const AppNavigationContent(),
            ),
          Expanded(child: child),
        ],
      ),
    );
  }
}
