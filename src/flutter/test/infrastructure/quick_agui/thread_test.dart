import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/infrastructure/quick_agui/run.dart';
import 'package:soliplex_client/infrastructure/quick_agui/thread.dart';

void main() {
  group('Thread class', () {
    test('should accept an ID parameter in constructor', () {
      // Arrange
      const testId = 'thread-123';

      // Act
      final thread = Thread(id: testId);

      // Assert
      expect(thread, isNotNull);
      expect(thread, isA<Thread>());
    });

    test('should expose an iterable of Run objects', () {
      // Arrange
      const testId = 'thread-456';
      final thread = Thread(id: testId);

      // Act
      final runs = thread.runs;

      // Assert
      expect(runs, isNotNull);
      expect(runs, isA<Iterable<Run>>());
    });
  });
}
