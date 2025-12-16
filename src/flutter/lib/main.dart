import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/auth/web_auth_callback_stub.dart'
    if (dart.library.js_interop) 'package:soliplex/core/auth/web_auth_callback_web.dart'
    as platform;
import 'package:soliplex/core/router/app_router.dart';

void main() {
  // On web, capture auth callback params BEFORE GoRouter initializes.
  // GoRouter may modify window.location.hash when matching routes,
  // so we need to preserve the original URL params.
  if (kIsWeb) {
    platform.captureCallbackParamsEarly();
  }

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
