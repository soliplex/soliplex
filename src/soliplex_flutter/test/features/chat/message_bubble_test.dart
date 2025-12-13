import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/client/client.dart';
import 'package:soliplex_flutter/features/chat/message_bubble.dart';

void main() {
  Widget wrapWidget(Widget widget) {
    return MaterialApp(home: Scaffold(body: widget));
  }

  group('MessageBubble', () {
    testWidgets('renders text bubble for text message', (tester) async {
      final message = ChatMessage.text(
        user: ChatUser.assistant,
        text: 'Hello world',
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('Hello world'), findsOneWidget);
    });

    testWidgets('renders error bubble for error message', (tester) async {
      final message = ChatMessage.error(
        message: 'Something went wrong',
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.text('Something went wrong'), findsOneWidget);
    });

    testWidgets('renders tool call bubble for tool call message', (tester) async {
      final message = ChatMessage.toolCall(
        toolCalls: [
          ToolCallInfo(
            id: 'tc1',
            name: 'search',
            status: ToolCallStatus.completed,
          ),
        ],
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byIcon(Icons.build), findsOneWidget);
      expect(find.text('search'), findsOneWidget);
    });

    testWidgets('renders genui bubble for genui message', (tester) async {
      final message = ChatMessage.genUi(
        widgetName: 'TestWidget',
        data: {},
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byIcon(Icons.widgets), findsOneWidget);
      expect(find.textContaining('GenUI: TestWidget'), findsOneWidget);
    });

    testWidgets('renders loading bubble for loading message', (tester) async {
      final message = ChatMessage(
        id: 'loading1',
        user: ChatUser.assistant,
        type: MessageType.loading,
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  group('_TextBubble', () {
    testWidgets('displays user message on right side', (tester) async {
      final message = ChatMessage.text(
        user: ChatUser.user,
        text: 'User message',
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('User message'), findsOneWidget);
      expect(find.byIcon(Icons.person), findsOneWidget);
    });

    testWidgets('displays assistant message on left side', (tester) async {
      final message = ChatMessage.text(
        user: ChatUser.assistant,
        text: 'Assistant message',
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('Assistant message'), findsOneWidget);
      expect(find.byIcon(Icons.smart_toy), findsOneWidget);
    });

    testWidgets('displays streaming indicator', (tester) async {
      final message = ChatMessage.text(
        user: ChatUser.assistant,
        text: 'Streaming...',
        isStreaming: true,
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byType(CircularProgressIndicator), findsWidgets);
    });

    testWidgets('displays collapsible thinking section', (tester) async {
      final message = ChatMessage(
        id: 'msg1',
        user: ChatUser.assistant,
        type: MessageType.text,
        text: 'Response',
        thinkingText: 'Let me think about this...',
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      // Thinking section should be present
      expect(find.text('Thinking'), findsOneWidget);
      expect(find.byIcon(Icons.psychology), findsOneWidget);
      expect(find.byIcon(Icons.expand_more), findsOneWidget);

      // Content should be collapsed initially
      expect(find.text('Let me think about this...'), findsNothing);

      // Tap to expand
      await tester.tap(find.text('Thinking'));
      await tester.pumpAndSettle();

      // Content should now be visible
      expect(find.text('Let me think about this...'), findsOneWidget);
      expect(find.byIcon(Icons.expand_less), findsOneWidget);

      // Tap to collapse
      await tester.tap(find.text('Thinking'));
      await tester.pumpAndSettle();

      // Content should be hidden again
      expect(find.text('Let me think about this...'), findsNothing);
    });

    testWidgets('displays thinking streaming indicator', (tester) async {
      final message = ChatMessage(
        id: 'msg1',
        user: ChatUser.assistant,
        type: MessageType.text,
        text: 'Response',
        thinkingText: 'Thinking...',
        isThinkingStreaming: true,
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('Thinking'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsWidgets);
    });

    testWidgets('does not show thinking section when text is empty', (tester) async {
      final message = ChatMessage(
        id: 'msg1',
        user: ChatUser.assistant,
        type: MessageType.text,
        text: 'Response',
        thinkingText: '',
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('Thinking'), findsNothing);
    });
  });

  group('_ErrorBubble', () {
    testWidgets('displays error message', (tester) async {
      final message = ChatMessage.error(
        message: 'Network error occurred',
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.text('Network error occurred'), findsOneWidget);
    });

    testWidgets('displays default message when error message is null', (tester) async {
      final message = ChatMessage(
        id: 'err1',
        user: ChatUser.system,
        type: MessageType.error,
        errorMessage: null,
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('An error occurred'), findsOneWidget);
    });
  });

  group('_ToolCallBubble', () {
    testWidgets('displays multiple tool calls', (tester) async {
      final message = ChatMessage.toolCall(
        toolCalls: [
          ToolCallInfo(
            id: 'tc1',
            name: 'search',
            status: ToolCallStatus.completed,
          ),
          ToolCallInfo(
            id: 'tc2',
            name: 'analyze',
            status: ToolCallStatus.executing,
          ),
        ],
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byIcon(Icons.build), findsOneWidget);
      expect(find.text('search'), findsOneWidget);
      expect(find.text('analyze'), findsOneWidget);
    });

    testWidgets('displays tool icon', (tester) async {
      final message = ChatMessage.toolCall(
        toolCalls: [
          ToolCallInfo(
            id: 'tc1',
            name: 'test',
            status: ToolCallStatus.pending,
          ),
        ],
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      // Check for avatar with build icon
      final avatar = tester.widget<CircleAvatar>(
        find.ancestor(
          of: find.byIcon(Icons.build),
          matching: find.byType(CircleAvatar),
        ),
      );
      expect(avatar, isNotNull);
    });
  });

  group('_ToolCallChip', () {
    testWidgets('displays pending status', (tester) async {
      final message = ChatMessage.toolCall(
        toolCalls: [
          ToolCallInfo(
            id: 'tc1',
            name: 'pending_tool',
            status: ToolCallStatus.pending,
          ),
        ],
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('pending_tool'), findsOneWidget);
      expect(find.byIcon(Icons.hourglass_empty), findsOneWidget);
    });

    testWidgets('displays executing status', (tester) async {
      final message = ChatMessage.toolCall(
        toolCalls: [
          ToolCallInfo(
            id: 'tc1',
            name: 'executing_tool',
            status: ToolCallStatus.executing,
          ),
        ],
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('executing_tool'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('displays completed status', (tester) async {
      final message = ChatMessage.toolCall(
        toolCalls: [
          ToolCallInfo(
            id: 'tc1',
            name: 'completed_tool',
            status: ToolCallStatus.completed,
          ),
        ],
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('completed_tool'), findsOneWidget);
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    testWidgets('displays failed status', (tester) async {
      final message = ChatMessage.toolCall(
        toolCalls: [
          ToolCallInfo(
            id: 'tc1',
            name: 'failed_tool',
            status: ToolCallStatus.failed,
          ),
        ],
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.text('failed_tool'), findsOneWidget);
      expect(find.byIcon(Icons.error), findsOneWidget);
    });
  });

  group('_GenUiBubble', () {
    testWidgets('displays widget name', (tester) async {
      final message = ChatMessage.genUi(
        widgetName: 'CustomChart',
        data: {},
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byIcon(Icons.widgets), findsOneWidget);
      expect(find.textContaining('GenUI: CustomChart'), findsOneWidget);
      expect(find.text('Interactive widget rendered'), findsOneWidget);
    });

    testWidgets('displays Unknown when widget_name is missing', (tester) async {
      final message = ChatMessage(
        id: 'genui1',
        user: ChatUser.assistant,
        type: MessageType.genUi,
        data: {},
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.textContaining('GenUI: Unknown'), findsOneWidget);
    });
  });

  group('_LoadingBubble', () {
    testWidgets('displays loading indicator', (tester) async {
      final message = ChatMessage(
        id: 'loading1',
        user: ChatUser.assistant,
        type: MessageType.loading,
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      expect(find.byIcon(Icons.smart_toy), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('displays assistant avatar', (tester) async {
      final message = ChatMessage(
        id: 'loading1',
        user: ChatUser.assistant,
        type: MessageType.loading,
        createdAt: DateTime.now(),
      );

      await tester.pumpWidget(wrapWidget(MessageBubble(message: message)));

      final avatar = tester.widget<CircleAvatar>(
        find.ancestor(
          of: find.byIcon(Icons.smart_toy),
          matching: find.byType(CircleAvatar),
        ),
      );
      expect(avatar, isNotNull);
    });
  });
}
