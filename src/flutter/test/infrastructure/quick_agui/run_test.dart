import 'package:ag_ui/ag_ui.dart' hide Run;
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/infrastructure/quick_agui/run.dart';

void main() {
  group('Run class', () {
    test('should be instantiable', () {
      // Arrange & Act
      final run = Run(id: 'run-1');

      // Assert
      expect(run, isNotNull);
      expect(run, isA<Run>());
    });

    test('should accept an id parameter and expose it', () {
      // Arrange
      const testId = 'run-123';

      // Act
      final run = Run(id: testId);

      // Assert
      expect(run.id, equals('run-123'));
    });

    test('should have an empty message list initially', () {
      // Arrange & Act
      final run = Run(id: 'run-1');

      // Assert
      expect(run.messages, isNotNull);
      expect(run.messages, isEmpty);
    });
  });
}
