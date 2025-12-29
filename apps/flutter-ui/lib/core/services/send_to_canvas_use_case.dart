import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/canvas_content_service.dart';

/// Provider for SendToCanvasUseCase.
final sendToCanvasUseCaseProvider = Provider<SendToCanvasUseCase>((ref) {
  return SendToCanvasUseCase(ref);
});

/// Result of sending content to the canvas.
sealed class SendToCanvasResult {
  const SendToCanvasResult();
}

/// Content was successfully sent to the canvas.
class SendToCanvasSuccess extends SendToCanvasResult {
  const SendToCanvasSuccess(this.widgetName);

  /// The widget name that was added to the canvas.
  final String widgetName;
}

/// Failed to send content to the canvas.
class SendToCanvasFailure extends SendToCanvasResult {
  const SendToCanvasFailure(this.error);

  /// Error message describing the failure.
  final String error;
}

/// Use case for sending message content to the canvas.
///
/// Extracts the "send to canvas" logic from UI widgets into a testable service.
/// Handles both GenUI widgets (direct pass-through) and text content (analyzed
/// and converted to appropriate canvas widget).
///
/// Usage:
/// ```dart
/// final useCase = ref.read(sendToCanvasUseCaseProvider);
/// final result = useCase.execute(
///   content: message.text,
///   sourceMessageId: message.id,
/// );
/// if (result is SendToCanvasSuccess) {
///   // Show success feedback
/// }
/// ```
class SendToCanvasUseCase {
  SendToCanvasUseCase(this._ref, {CanvasContentService? contentService})
    : _contentService = contentService ?? CanvasContentService();
  final Ref _ref;
  final CanvasContentService _contentService;

  /// Send content to the canvas.
  ///
  /// If [genUiContent] is provided, sends the GenUI widget directly.
  /// Otherwise, analyzes [content] and converts to appropriate canvas widget.
  ///
  /// Returns SendToCanvasSuccess with the widget name on success,
  /// or SendToCanvasFailure with an error message on failure.
  SendToCanvasResult execute({
    required String content,
    String? sourceMessageId,
    GenUiContent? genUiContent,
  }) {
    try {
      final canvasNotifier = _ref.read(activeCanvasNotifierProvider);

      if (canvasNotifier == null) {
        return const SendToCanvasFailure('No active canvas available');
      }

      // For GenUI widgets, send directly without analysis
      if (genUiContent != null) {
        canvasNotifier.addItem(genUiContent.widgetName, genUiContent.data);
        return SendToCanvasSuccess(genUiContent.widgetName);
      }

      // For text content, analyze and convert
      if (content.isEmpty) {
        return const SendToCanvasFailure('Content is empty');
      }

      final analysis = _contentService.analyze(
        content,
        sourceMessageId: sourceMessageId,
      );

      canvasNotifier.addItem(analysis.widgetName, analysis.data);
      return SendToCanvasSuccess(analysis.widgetName);
    } on Object catch (e) {
      return SendToCanvasFailure(e.toString());
    }
  }
}
