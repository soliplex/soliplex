import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';

/// Provider for application configuration.
///
/// AM1: Returns default hardcoded config.
/// AM7: Load from secure storage.
final configProvider = StateProvider<AppConfig>((ref) {
  return AppConfig.defaults();
});
