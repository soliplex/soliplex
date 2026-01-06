import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/features/rooms/rooms_screen.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';
import 'package:soliplex_frontend/shared/widgets/loading_indicator.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('RoomsScreen', () {
    testWidgets('displays loading indicator while fetching', (tester) async {
      // Use a completer to control when the async operation completes
      final completer = Completer<List<Room>>();

      await tester.pumpWidget(
        createTestApp(
          home: const RoomsScreen(),
          overrides: [
            roomsProvider.overrideWith((ref) => completer.future),
          ],
        ),
      );

      // Before async operation completes, should show loading
      expect(find.byType(LoadingIndicator), findsOneWidget);

      // Complete the future and settle
      completer.complete([]);
      await tester.pumpAndSettle();
    });

    testWidgets('displays room list when loaded', (tester) async {
      final mockRooms = [
        TestData.createRoom(id: 'room1', name: 'Room 1'),
        TestData.createRoom(id: 'room2', name: 'Room 2'),
      ];

      await tester.pumpWidget(
        createTestApp(
          home: const RoomsScreen(),
          overrides: [
            roomsProvider.overrideWith((ref) async => mockRooms),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Room 1'), findsOneWidget);
      expect(find.text('Room 2'), findsOneWidget);
    });

    testWidgets('displays empty state when no rooms', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const RoomsScreen(),
          overrides: [
            roomsProvider.overrideWith((ref) async => []),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(EmptyState), findsOneWidget);
      expect(find.text('No rooms available'), findsOneWidget);
    });
  });
}
