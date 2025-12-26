import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

void main() {
  group('lastViewedThreadProvider', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('returns NoLastViewed when no thread was viewed for room', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final lastViewed = await container.read(
        lastViewedThreadProvider('room-1').future,
      );

      expect(lastViewed, isA<NoLastViewed>());
    });

    test('returns HasLastViewed with thread for room', () async {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-1': 'thread-123',
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      final lastViewed = await container.read(
        lastViewedThreadProvider('room-1').future,
      );

      expect(lastViewed, isA<HasLastViewed>());
      expect((lastViewed as HasLastViewed).threadId, 'thread-123');
    });

    test('returns different threads for different rooms', () async {
      SharedPreferences.setMockInitialValues({
        'lastViewedThread_room-1': 'thread-a',
        'lastViewedThread_room-2': 'thread-b',
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      final lastViewed1 = await container.read(
        lastViewedThreadProvider('room-1').future,
      );
      final lastViewed2 = await container.read(
        lastViewedThreadProvider('room-2').future,
      );

      expect((lastViewed1 as HasLastViewed).threadId, 'thread-a');
      expect((lastViewed2 as HasLastViewed).threadId, 'thread-b');
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

      // Initially NoLastViewed
      var lastViewed = await container.read(
        lastViewedThreadProvider('room-1').future,
      );
      expect(lastViewed, isA<NoLastViewed>());

      // Set value
      await container.read(
        _setLastViewedThreadTestProvider(
          (roomId: 'room-1', threadId: 'thread-789'),
        ).future,
      );

      // Re-read - should see new value
      lastViewed = await container.read(
        lastViewedThreadProvider('room-1').future,
      );
      expect((lastViewed as HasLastViewed).threadId, 'thread-789');
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

  group('invalidateLastViewed', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    testWidgets('creates working callback from WidgetRef', (tester) async {
      // Track invalidation calls
      final invalidateCalls = <String>[];

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Consumer(
              builder: (context, ref, _) {
                return ElevatedButton(
                  onPressed: () async {
                    // Use the actual invalidateLastViewed helper
                    final invalidate = invalidateLastViewed(ref);

                    // Call setLastViewedThread with the helper
                    await setLastViewedThread(
                      roomId: 'room-1',
                      threadId: 'thread-widget-test',
                      invalidate: (roomId) {
                        invalidateCalls.add(roomId);
                        invalidate(roomId);
                      },
                    );
                  },
                  child: const Text('Test'),
                );
              },
            ),
          ),
        ),
      );

      // Tap the button to trigger the test
      await tester.tap(find.text('Test'));
      await tester.pumpAndSettle();

      // Verify SharedPreferences was written
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('lastViewedThread_room-1'), 'thread-widget-test');

      // Verify invalidation callback was invoked
      expect(invalidateCalls, ['room-1']);
    });

    testWidgets('invalidates provider so new value is visible', (tester) async {
      LastViewed? readValue;

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Consumer(
              builder: (context, ref, _) {
                return Column(
                  children: [
                    ElevatedButton(
                      key: const Key('write'),
                      onPressed: () async {
                        await setLastViewedThread(
                          roomId: 'room-2',
                          threadId: 'thread-new',
                          invalidate: invalidateLastViewed(ref),
                        );
                      },
                      child: const Text('Write'),
                    ),
                    ElevatedButton(
                      key: const Key('read'),
                      onPressed: () async {
                        readValue = await ref.read(
                          lastViewedThreadProvider('room-2').future,
                        );
                      },
                      child: const Text('Read'),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      );

      // Write value
      await tester.tap(find.byKey(const Key('write')));
      await tester.pumpAndSettle();

      // Read value - should see the new value after invalidation
      await tester.tap(find.byKey(const Key('read')));
      await tester.pumpAndSettle();

      expect((readValue! as HasLastViewed).threadId, 'thread-new');
    });
  });
}

// Test helper providers to access Ref for testing functions
final _setLastViewedThreadTestProvider =
    FutureProvider.family<void, ({String roomId, String threadId})>(
  (ref, args) => setLastViewedThread(
    roomId: args.roomId,
    threadId: args.threadId,
    invalidate: (roomId) => ref.invalidate(lastViewedThreadProvider(roomId)),
  ),
);

final _clearLastViewedThreadTestProvider = FutureProvider.family<void, String>(
  (ref, roomId) => clearLastViewedThread(
    roomId: roomId,
    invalidate: (id) => ref.invalidate(lastViewedThreadProvider(id)),
  ),
);
