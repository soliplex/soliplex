import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Callback when a link is tapped in markdown
typedef LinkTapCallback =
    void Function(String? href, String text, String messageId);

/// Callback when an image load state changes
typedef ImageLoadCallback =
    void Function(String imageUrl, String messageId, ImageLoadState state);

/// Callback when code is copied from a code block
typedef CodeCopyCallback =
    void Function(String code, String? language, String messageId);

/// Callback when text is quoted
typedef QuoteCallback = void Function(String quotedText, String messageId);

/// Callback when all images in a message finish loading
typedef AllImagesLoadedCallback = void Function(String messageId);

/// Image loading state
enum ImageLoadState { loading, loaded, error }

/// Central registry for markdown interaction hooks.
///
/// This class provides a centralized place to register callbacks for
/// various markdown interactions like link taps, image loads, code copying,
/// and text quoting.
///
/// Example usage:
/// ```dart
/// final hooks = ref.read(markdownHooksProvider);
/// hooks.onLinkTap = (href, text, messageId) {
///   if (href != null) launchUrl(Uri.parse(href));
/// };
/// ```
class MarkdownHooks {
  /// Called when a link is tapped in markdown content.
  ///
  /// Parameters:
  /// - `href`: The URL of the link (may be null for malformed links)
  /// - `text`: The display text of the link
  /// - `messageId`: The ID of the message containing the link
  LinkTapCallback? onLinkTap;

  /// Called when an image load state changes.
  ///
  /// Fires for each image when it starts loading, finishes loading,
  /// or encounters an error.
  ImageLoadCallback? onImageLoad;

  /// Called when all images in a message are loaded (or errored).
  ///
  /// Useful for knowing when it's safe to scroll without layout shifts.
  AllImagesLoadedCallback? onAllImagesLoaded;

  /// Called when code is copied from a code block.
  ///
  /// Parameters:
  /// - `code`: The copied code content
  /// - `language`: The language identifier (e.g., 'dart', 'python')
  /// - `messageId`: The ID of the message containing the code block
  CodeCopyCallback? onCodeCopy;

  /// Called when text is quoted from markdown content.
  ///
  /// The quoted text is already formatted with `> ` prefixes.
  QuoteCallback? onQuote;

  /// Called when streaming animation completes for a message.
  VoidCallback? onStreamingComplete;
}

/// Riverpod provider for markdown hooks.
///
/// This creates a single instance of MarkdownHooks that can be accessed
/// throughout the app to register and trigger callbacks.
final markdownHooksProvider = Provider<MarkdownHooks>((ref) {
  return MarkdownHooks();
});
