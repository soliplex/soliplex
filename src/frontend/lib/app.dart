import 'package:flutter/material.dart';
import 'package:soliplex_frontend/core/router/app_router.dart';

/// Root application widget.
class SoliplexApp extends StatelessWidget {
  const SoliplexApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Soliplex',
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
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}
