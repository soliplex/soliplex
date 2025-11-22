import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/infrastructure/quick_agui/run.dart';

void main() {
  group('Run class', () {
    test('should be instantiable', () {
      // Arrange & Act
      final run = Run();

      // Assert
      expect(run, isNotNull);
      expect(run, isA<Run>());
    });
  });
}
