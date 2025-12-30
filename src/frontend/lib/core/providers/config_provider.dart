import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';

/// Notifier for application configuration.
class ConfigNotifier extends Notifier<AppConfig> {
  @override
  AppConfig build() => AppConfig.defaults();

  /// The current configuration.
  AppConfig get current => state;

  /// Updates the configuration.
  set current(AppConfig value) => state = value;
}

/// Provider for application configuration.
///
/// AM1: Returns default hardcoded config.
/// AM7: Load from secure storage.
final configProvider =
    NotifierProvider<ConfigNotifier, AppConfig>(ConfigNotifier.new);
