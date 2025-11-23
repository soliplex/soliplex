import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/infrastructure/quick_agui/run.dart';
import 'package:soliplex_client/infrastructure/quick_agui/thread.dart';

void main() {
  group('Initialised Thread', () {
    test('is constructed with a thread id', () {
      // Arrange
      const testId = 'thread-123';

      // Act
      final thread = Thread(id: testId);

      // Assert
      expect(thread, isNotNull);
      expect(thread, isA<Thread>());
    });

    test('exposes an empty iterable of Run objects', () {
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
