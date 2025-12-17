import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';

void main() {
  group('AppConfig', () {
    test('defaults factory creates config', () {
      final config = AppConfig.defaults();

      expect(config.baseUrl, 'http://localhost:8000');
      expect(config.appName, 'Soliplex');
      expect(config.version, '1.0.0-dev');
    });

    test('copyWith replaces baseUrl', () {
      final config = AppConfig.defaults();
      final updated = config.copyWith(baseUrl: 'http://example.com:9000');

      expect(updated.baseUrl, 'http://example.com:9000');
      expect(updated.appName, 'Soliplex');
      expect(updated.version, '1.0.0-dev');
    });

    test('copyWith replaces appName', () {
      final config = AppConfig.defaults();
      final updated = config.copyWith(appName: 'Custom App');

      expect(updated.baseUrl, 'http://localhost:8000');
      expect(updated.appName, 'Custom App');
      expect(updated.version, '1.0.0-dev');
    });

    test('copyWith replaces version', () {
      final config = AppConfig.defaults();
      final updated = config.copyWith(version: '2.0.0');

      expect(updated.baseUrl, 'http://localhost:8000');
      expect(updated.appName, 'Soliplex');
      expect(updated.version, '2.0.0');
    });
  });
}
