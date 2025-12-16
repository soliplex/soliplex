import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/router/app_router.dart';

void main() {
  // Use hash-based URLs on web (e.g., /#/chat)
  // This is Flutter's default - no special configuration needed
  // OIDC callback redirects to /?token=... and hash routing handles the rest
  runApp(const ProviderScope(child: AgUiDashApp()));
}

class AgUiDashApp extends ConsumerWidget {
  const AgUiDashApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'AG-UI Dashboard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
        ),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      routerConfig: router,
    );
  }
}
