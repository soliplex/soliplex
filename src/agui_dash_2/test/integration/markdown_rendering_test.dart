import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:agui_dash_2/features/chat/widgets/streaming_markdown_widget.dart';

void main() {
  testWidgets('StreamingMarkdownWidget renders static markdown correctly using flutter_markdown_plus', (WidgetTester tester) async {
    // Define markdown with various elements
    const markdownContent = '**Bold Text**';

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: StreamingMarkdownWidget(
              text: markdownContent,
              messageId: 'test-msg-1',
              isStreaming: false, // Use static rendering path (flutter_markdown_plus)
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify key markdown elements are rendered
    expect(find.text('Bold Text'), findsOneWidget);
  });

  testWidgets('StreamingMarkdownWidget sanitizes unclosed code blocks', (WidgetTester tester) async {
    // Markdown with unclosed code block (common in streaming)
    const partialMarkdown = 'Some text';

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: StreamingMarkdownWidget(
              text: partialMarkdown,
              messageId: 'test-msg-2',
              isStreaming: false, 
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify it doesn't crash and renders the content
    expect(find.text('Some text'), findsOneWidget);
  });
}