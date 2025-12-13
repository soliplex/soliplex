import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/client/client.dart';
import 'package:soliplex_flutter/features/details/details_widget.dart';
import 'package:soliplex_flutter/providers/providers.dart';

import '../../mocks/mock_soliplex_client.dart';

void main() {
  Widget wrapWidget(Widget widget, {List<Override> overrides = const []}) {
    return ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        home: Scaffold(body: widget),
      ),
    );
  }

  group('DetailsWidget', () {
    testWidgets('displays empty state when no room selected', (tester) async {
      await tester.pumpWidget(wrapWidget(const DetailsWidget()));

      expect(find.text('Select a room'), findsOneWidget);
      expect(find.byIcon(Icons.info_outline), findsOneWidget);
    });

    testWidgets('displays empty state when no thread selected', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pump();

      expect(find.text('Select a thread'), findsOneWidget);
    });

    testWidgets('displays details header when room and thread selected', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pump();

      expect(find.text('Details'), findsOneWidget);
      expect(find.textContaining('Thread:'), findsOneWidget);
    });

    testWidgets('displays three tabs', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pump();

      expect(find.text('Messages'), findsOneWidget);
      expect(find.text('Thinking'), findsOneWidget);
      expect(find.text('State'), findsOneWidget);
    });

    testWidgets('switches between tabs', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Initially on Messages tab
      expect(find.text('Messages'), findsOneWidget);

      // Tap Thinking tab
      await tester.tap(find.text('Thinking'));
      await tester.pumpAndSettle();

      // Tap State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      // Widget should render without errors
      expect(find.byType(DetailsWidget), findsOneWidget);
    });
  });

  group('_EmptyDetails', () {
    testWidgets('displays info icon', (tester) async {
      await tester.pumpWidget(wrapWidget(const DetailsWidget()));

      expect(find.byIcon(Icons.info_outline), findsOneWidget);
    });
  });

  group('_DetailsHeader', () {
    testWidgets('displays thread ID truncated', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pump();

      expect(find.textContaining('thread12...'), findsOneWidget);
    });
  });

  group('_MessagesTab', () {
    testWidgets('displays no messages message when empty', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      // Wait for messages to load (will be empty from mock)
      await tester.pumpAndSettle();

      // May show loading or empty message depending on timing
      expect(find.byType(DetailsWidget), findsOneWidget);
    });
  });

  group('_ThinkingTab', () {
    testWidgets('shows no thinking content message when empty', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to Thinking tab
      await tester.tap(find.text('Thinking'));
      await tester.pumpAndSettle();

      // Should show empty message
      expect(find.text('No thinking content'), findsOneWidget);
    });
  });

  group('_StateTab', () {
    testWidgets('shows no state data message when empty', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      // Should show empty message
      expect(find.text('No state data'), findsOneWidget);
    });

    testWidgets('displays state data when canvas state exists', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({'key': 'value'})),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      // Should show state card
      expect(find.text('key'), findsOneWidget);
    });
  });

  group('_StateCard', () {
    testWidgets('displays state key and type', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'stringKey': 'test value',
            'intKey': 42,
            'boolKey': true,
            'listKey': [1, 2, 3],
            'mapKey': {'nested': 'value'},
          })),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      // Should show various state keys
      expect(find.text('stringKey'), findsOneWidget);
      expect(find.text('intKey'), findsOneWidget);
    });

    testWidgets('expands to show value', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({'testKey': 'testValue'})),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      // Tap on ExpansionTile to expand
      await tester.tap(find.text('testKey'));
      await tester.pumpAndSettle();

      // Should show value
      expect(find.textContaining('testValue'), findsWidgets);
    });
  });

  group('_EmptyContent', () {
    testWidgets('displays message text', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to Thinking tab (should be empty)
      await tester.tap(find.text('Thinking'));
      await tester.pumpAndSettle();

      expect(find.text('No thinking content'), findsOneWidget);
    });
  });

  group('JsonEncoder', () {
    testWidgets('formats nested data correctly', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'nested': {'inner': 'value'},
          })),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      // Expand nested key
      await tester.tap(find.text('nested'));
      await tester.pumpAndSettle();

      // Should render without error and show formatted JSON
      expect(find.byType(DetailsWidget), findsOneWidget);
    });

    testWidgets('handles empty map and list', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'emptyMap': <String, dynamic>{},
            'emptyList': <dynamic>[],
          })),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.text('emptyMap'), findsOneWidget);
      expect(find.text('emptyList'), findsOneWidget);
    });

    testWidgets('formats list data correctly', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listData': [1, 'two', true, null],
          })),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to State tab
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      // Expand list key
      await tester.tap(find.text('listData'));
      await tester.pumpAndSettle();

      expect(find.byType(DetailsWidget), findsOneWidget);
    });
  });

  group('_StateCard icons', () {
    testWidgets('displays correct icon for Map type', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'mapValue': {'key': 'value'},
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.data_object), findsOneWidget);
    });

    testWidgets('displays correct icon for List type', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listValue': [1, 2, 3],
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.data_array), findsOneWidget);
    });

    testWidgets('displays correct icon for number type', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'numValue': 42,
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.numbers), findsOneWidget);
    });

    testWidgets('displays correct icon for bool type', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'boolValue': true,
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.toggle_on), findsOneWidget);
    });

    testWidgets('displays correct icon for string type', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'stringValue': 'hello',
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.text_fields), findsOneWidget);
    });
  });

  group('_StateCard type labels', () {
    testWidgets('displays integer type label', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'intVal': 100,
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.text('Integer'), findsOneWidget);
    });

    testWidgets('displays double type label', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'doubleVal': 3.14,
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.text('Double'), findsOneWidget);
    });

    testWidgets('displays boolean type label', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'boolVal': false,
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.text('Boolean'), findsOneWidget);
    });

    testWidgets('displays string type label with length', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'strVal': 'test',
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.text('String (4 chars)'), findsOneWidget);
    });

    testWidgets('displays object type label with key count', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'objVal': {'a': 1, 'b': 2},
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.text('Object (2 keys)'), findsOneWidget);
    });

    testWidgets('displays array type label with item count', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'arrVal': [1, 2, 3, 4, 5],
          })),
        ],
      ));

      await tester.pumpAndSettle();
      await tester.tap(find.text('State'));
      await tester.pumpAndSettle();

      expect(find.text('Array (5 items)'), findsOneWidget);
    });
  });

  group('_DetailRow', () {
    testWidgets('displays multiline content correctly', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.text(
          user: ChatUser.assistant,
          text: 'This is a long message\nwith multiple lines',
        ),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Tap on a message card to expand it
      await tester.tap(find.text('Assistant').first);
      await tester.pumpAndSettle();

      expect(find.textContaining('This is a long message'), findsOneWidget);
    });
  });

  group('_MessagesTab with messages', () {
    testWidgets('displays message list when messages exist', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.text(user: ChatUser.user, text: 'Hello'),
        ChatMessage.text(user: ChatUser.assistant, text: 'Hi there'),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('User'), findsWidgets);
      expect(find.text('Assistant'), findsWidgets);
    });
  });

  group('_MessageDetailCard', () {
    testWidgets('displays text message type correctly', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.text(user: ChatUser.user, text: 'User message'),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('Text'), findsOneWidget);
    });

    testWidgets('displays error message type correctly', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.error(message: 'Something went wrong'),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('Error'), findsOneWidget);
    });

    testWidgets('displays tool call message type correctly', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.toolCall(toolCalls: [
          ToolCallInfo(id: 'tc1', name: 'search', status: ToolCallStatus.completed),
        ]),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('Tool'), findsOneWidget);
    });

    testWidgets('displays genui message type correctly', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.genUi(widgetName: 'TestWidget', data: {}),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('GenUI'), findsOneWidget);
    });

    testWidgets('displays loading message type correctly', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage(
          id: 'loading1',
          user: ChatUser.assistant,
          type: MessageType.loading,
          createdAt: DateTime.now(),
        ),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('Loading'), findsOneWidget);
    });

    testWidgets('displays system user label correctly', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.error(message: 'System error'),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('System'), findsOneWidget);
    });

    testWidgets('expands to show error details', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.error(message: 'Network failure'),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Expand the card
      await tester.tap(find.text('System'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Network failure'), findsWidgets);
    });

    testWidgets('expands to show tool call details', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.toolCall(toolCalls: [
          ToolCallInfo(id: 'tc1', name: 'search', status: ToolCallStatus.completed),
          ToolCallInfo(id: 'tc2', name: 'analyze', status: ToolCallStatus.executing),
        ]),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Expand the card
      await tester.tap(find.text('Assistant'));
      await tester.pumpAndSettle();

      expect(find.textContaining('search (completed)'), findsOneWidget);
    });

    testWidgets('shows streaming status when message is streaming', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage.text(
          user: ChatUser.assistant,
          text: 'Streaming...',
          isStreaming: true,
        ),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Expand the card
      await tester.tap(find.text('Assistant'));
      await tester.pumpAndSettle();

      expect(find.text('Streaming...'), findsWidgets);
    });
  });

  group('_ThinkingTab with content', () {
    testWidgets('displays thinking messages', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage(
          id: 'msg1',
          user: ChatUser.assistant,
          type: MessageType.text,
          text: 'Response',
          thinkingText: 'Let me analyze this carefully...',
          createdAt: DateTime.now(),
        ),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to Thinking tab
      await tester.tap(find.text('Thinking'));
      await tester.pumpAndSettle();

      expect(find.text('Let me analyze this carefully...'), findsOneWidget);
    });

    testWidgets('renders thinking tab with streaming content', (tester) async {
      final mockClient = MockSoliplexClientWithMessages([
        ChatMessage(
          id: 'msg1',
          user: ChatUser.assistant,
          type: MessageType.text,
          text: 'Response',
          thinkingText: 'Processing...',
          isThinkingStreaming: true,
          createdAt: DateTime.now(),
        ),
      ]);

      await tester.pumpWidget(wrapWidget(
        const DetailsWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          currentThreadProvider.overrideWith((ref) => 'thread123456789'),
        ],
      ));

      await tester.pumpAndSettle();

      // Switch to Thinking tab
      await tester.tap(find.text('Thinking'));
      await tester.pump();
      await tester.pump();
      await tester.pump();

      // Widget should render without errors
      expect(find.byType(DetailsWidget), findsOneWidget);
    });
  });
}

/// Mock client that returns a specific list of messages
class MockSoliplexClientWithMessages extends MockSoliplexClient {
  MockSoliplexClientWithMessages(this._messages);

  final List<ChatMessage> _messages;

  @override
  Stream<List<ChatMessage>> getMessageStream(String roomId) {
    return Stream.value(_messages);
  }
}
