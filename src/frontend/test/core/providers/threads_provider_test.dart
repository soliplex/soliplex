import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

void main() {
  group('threadsProvider', () {
    test('returns threads for general room', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final threads = await container.read(threadsProvider('general').future);

      expect(threads, hasLength(5));
      expect(threads.every((t) => t.roomId == 'general'), isTrue);
    });

    test('returns threads for technical room', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final threads = await container.read(threadsProvider('technical').future);

      expect(threads, hasLength(4));
      expect(threads.every((t) => t.roomId == 'technical'), isTrue);
    });

    test('returns empty list for unknown room', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final threads = await container.read(threadsProvider('unknown').future);

      expect(threads, isEmpty);
    });
  });
}
