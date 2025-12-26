import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

void main() {
  group('lastViewedThreadProvider', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('returns null when no thread was viewed for room', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final threadId = await container.read(
        lastViewedThreadProvider('room-1').future,
      );

      expect(threadId, isNull);
    });

    test('returns last viewed thread for room', () async {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-1': 'thread-123',
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      final threadId = await container.read(
        lastViewedThreadProvider('room-1').future,
      );

      expect(threadId, 'thread-123');
    });

    test('returns different threads for different rooms', () async {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-1': 'thread-a',
        'lastViewedThread_room-2': 'thread-b',
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      final thread1 = await container.read(
        lastViewedThreadProvider('room-1').future,
      );
      final thread2 = await container.read(
        lastViewedThreadProvider('room-2').future,
      );

      expect(thread1, 'thread-a');
      expect(thread2, 'thread-b');
    });
  });

  group('setLastViewedThread', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('saves thread id to SharedPreferences', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Use a provider to get access to Ref
      await container.read(
        _setLastViewedThreadTestProvider(
          (roomId: 'room-1', threadId: 'thread-456'),
        ).future,
      );

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('lastViewedThread_room-1'), 'thread-456');
    });

    test('overwrites previous value for same room', () async {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-1': 'old-thread',
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      await container.read(
        _setLastViewedThreadTestProvider(
          (roomId: 'room-1', threadId: 'new-thread'),
        ).future,
      );

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('lastViewedThread_room-1'), 'new-thread');
    });

    test('does not affect other rooms', () async {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-2': 'thread-in-room-2',
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      await container.read(
        _setLastViewedThreadTestProvider(
          (roomId: 'room-1', threadId: 'thread-456'),
        ).future,
      );

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('lastViewedThread_room-1'), 'thread-456');
      expect(prefs.getString('lastViewedThread_room-2'), 'thread-in-room-2');
    });

    test('invalidates lastViewedThreadProvider for room', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Initially null
      var threadId = await container.read(
        lastViewedThreadProvider('room-1').future,
      );
      expect(threadId, isNull);

      // Set value
      await container.read(
        _setLastViewedThreadTestProvider(
          (roomId: 'room-1', threadId: 'thread-789'),
        ).future,
      );

      // Re-read - should see new value
      threadId = await container.read(
        lastViewedThreadProvider('room-1').future,
      );
      expect(threadId, 'thread-789');
    });
  });

  group('clearLastViewedThread', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-1': 'thread-123',
      });
    });

    test('removes thread from SharedPreferences', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      await container.read(_clearLastViewedThreadTestProvider('room-1').future);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('lastViewedThread_room-1'), isNull);
    });

    test('does not affect other rooms', () async {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-1': 'thread-a',
        'lastViewedThread_room-2': 'thread-b',
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      await container.read(_clearLastViewedThreadTestProvider('room-1').future);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('lastViewedThread_room-1'), isNull);
      expect(prefs.getString('lastViewedThread_room-2'), 'thread-b');
    });
  });
}

// Test helper providers to access Ref for testing functions
final _setLastViewedThreadTestProvider =
    FutureProvider.family<void, ({String roomId, String threadId})>(
  (ref, args) => setLastViewedThread(
    ref,
    roomId: args.roomId,
    threadId: args.threadId,
  ),
);

final _clearLastViewedThreadTestProvider =
    FutureProvider.family<void, String>(clearLastViewedThread);
