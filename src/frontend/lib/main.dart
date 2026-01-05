import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/app.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Clear stale keychain tokens on first launch after reinstall.
  // iOS preserves Keychain across uninstall/reinstall.
  await AuthStorage.clearOnReinstall();

  runApp(
    const ProviderScope(
      child: SoliplexApp(),
    ),
  );
}
