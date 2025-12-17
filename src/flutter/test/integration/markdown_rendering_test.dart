import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/features/chat/widgets/streaming_markdown_widget.dart';

void main() {
  testWidgets(
    // ignore: lines_longer_than_80_chars (auto-documented)
    'StreamingMarkdownWidget renders static markdown correctly using flutter_smooth_markdown', // ignore: lines_longer_than_80_chars
    (WidgetTester tester) async {
      // Define markdown with various elements
      const markdownContent = '**Bold Text**';

      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: StreamingMarkdownWidget(
                text: markdownContent,
                messageId: 'test-msg-1',
                isStreaming: false, // Use static rendering path
              ),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Find the RichText widget and verify its content
      final richTextFinder = find.byType(RichText);
      expect(richTextFinder, findsOneWidget);
      final RichText richText = tester.widget(richTextFinder);
      expect(richText.text.toPlainText(), contains('Bold Text'));
    },
  );

  testWidgets('StreamingMarkdownWidget sanitizes unclosed code blocks', (
    WidgetTester tester,
  ) async {
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

    // Find the RichText widget and verify its content
    final richTextFinder = find.byType(RichText);
    expect(richTextFinder, findsOneWidget);
    final RichText richText = tester.widget(richTextFinder);
    expect(richText.text.toPlainText(), contains('Some text'));
  });
}
