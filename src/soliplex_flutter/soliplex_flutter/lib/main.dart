import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_shell.dart';
import 'features/test_page/test_page_feature.dart';

void main() {
  runApp(const ProviderScope(child: SoliplexApp()));
}

/// Root application widget for Soliplex Flutter.
class SoliplexApp extends StatelessWidget {
  const SoliplexApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Soliplex',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => const AppShell(),
        '/test': (context) => const TestPage(),
      },
    );
  }
}
