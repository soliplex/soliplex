import 'package:flutter/material.dart';

import 'configure.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final app = await configure();
  runApp(app);
}
