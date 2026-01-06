import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/auth/auth_provider.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/router/app_router.dart';

/// Root application widget.
class SoliplexApp extends ConsumerWidget {
  const SoliplexApp({super.key});

  static final _theme = ThemeData(
    colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
    useMaterial3: true,
  );

  static final _darkTheme = ThemeData(
    colorScheme: ColorScheme.fromSeed(
      seedColor: Colors.blue,
      brightness: Brightness.dark,
    ),
    useMaterial3: true,
  );

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);

    // Don't construct routing until auth state is resolved.
    // This prevents building route widgets that would be discarded,
    // avoiding wasted work and premature provider side effects.
    if (authState is AuthLoading) {
      return MaterialApp(
        title: 'Soliplex',
        theme: _theme,
        darkTheme: _darkTheme,
        debugShowCheckedModeBanner: false,
        home: const _AuthLoadingScreen(),
      );
    }

    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'Soliplex',
      theme: _theme,
      darkTheme: _darkTheme,
      routerConfig: router,
      debugShowCheckedModeBanner: false,
    );
  }
}

/// Loading screen shown while auth session is being restored.
class _AuthLoadingScreen extends StatelessWidget {
  const _AuthLoadingScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Loading...'),
          ],
        ),
      ),
    );
  }
}
