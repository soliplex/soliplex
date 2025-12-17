import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/app.dart';

void main() {
  runApp(
    const ProviderScope(
      child: SoliplexApp(),
    ),
  );
}
