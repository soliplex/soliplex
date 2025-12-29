# Streaming Markdown Implementation Details

## Feature: Streaming Markdown with Hooks

**Status**: In Progress
**Date**: 2025-12-12

---

## Overview

Integrate `flutter_streaming_text_markdown` for streaming AI responses with a custom hook system for link taps, image completion tracking, and extensibility.

## User Requirements

- **Link handling**: Open in system browser via `url_launcher`
- **Image hooks**: Both per-image callbacks AND all-images-loaded tracking per message
- **Preserve features**: Copy/Quote context menus, styled code blocks with copy buttons

---

## Architecture

```
StreamingMarkdownWidget (wrapper)
├── Streaming mode: StreamingTextMarkdown.claude() for animation
└── Static mode: Custom MarkdownBody with full callbacks
    ├── onTapLink → url_launcher
    ├── ImageBuilder → TrackedImage with load callbacks
    └── CodeBlockBuilder → Styled code block with copy/quote
```

**Key insight**: `flutter_streaming_text_markdown` doesn't expose link/image callbacks. Strategy:
- Use it ONLY for streaming animation effect
- On finalization, switch to `flutter_markdown` with full callbacks
- Build image tracking layer that works in both modes

---

## Package Research

### flutter_streaming_text_markdown

**Source**: [pub.dev/packages/flutter_streaming_text_markdown](https://pub.dev/packages/flutter_streaming_text_markdown)

**Key Features**:
- `StreamingTextMarkdown.claude()` constructor - Claude-style animation
- `StreamingTextController` for programmatic control (pause, resume, skip)
- `onComplete` callback when animation finishes
- Built-in markdown rendering with `MarkdownStyleSheet` customization
- Theme support via `StreamingTextTheme`

**Constructor Parameters**:
- `text` (String): The text content to display
- `controller` (StreamingTextController?): For programmatic control
- `onComplete` (VoidCallback?): Executes when animation finishes
- `typingSpeed` (Duration): Controls animation velocity
- `wordByWord` (bool): Word-level vs character-level reveal
- `chunkSize` (int): Characters to reveal at once
- `fadeInEnabled` (bool): Activates fade transitions
- `fadeInDuration` (Duration): Fade animation length
- `markdownEnabled` (bool): Markdown rendering toggle
- `latexEnabled` (bool): Mathematical expression support
- `theme` (StreamingTextTheme?): Professional theming system

**StreamingTextController API**:
- Methods: `pause()`, `resume()`, `restart()`, `skipToEnd()`, `stop()`
- Properties: `isAnimating`, `isPaused`, `isCompleted`, `progress` (0.0-1.0), `state`
- Callbacks: `onStateChanged()`, `onProgressChanged()`, `onCompleted()`
- Speed: `speedMultiplier` property

**Limitations**:
- NO built-in `onTapLink` callback
- NO built-in `onImageLoad` callback
- Wraps flutter_markdown internally but doesn't expose its callbacks

---

## Files to Create

### 1. `lib/core/services/markdown_hooks.dart`

Callback registry and types:

```dart
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Callback when a link is tapped in markdown
typedef LinkTapCallback = void Function(
  String? href,
  String text,
  String messageId,
);

/// Callback when an image load state changes
typedef ImageLoadCallback = void Function(
  String imageUrl,
  String messageId,
  ImageLoadState state,
);

/// Callback when code is copied from a code block
typedef CodeCopyCallback = void Function(
  String code,
  String? language,
  String messageId,
);

/// Callback when text is quoted
typedef QuoteCallback = void Function(
  String quotedText,
  String messageId,
);

/// Callback when all images in a message finish loading
typedef AllImagesLoadedCallback = void Function(String messageId);

/// Image loading state
enum ImageLoadState { loading, loaded, error }

/// Central registry for markdown interaction hooks
class MarkdownHooks {
  /// Called when a link is tapped
  LinkTapCallback? onLinkTap;

  /// Called when an image load state changes
  ImageLoadCallback? onImageLoad;

  /// Called when all images in a message are loaded
  AllImagesLoadedCallback? onAllImagesLoaded;

  /// Called when code is copied from a code block
  CodeCopyCallback? onCodeCopy;

  /// Called when text is quoted
  QuoteCallback? onQuote;

  /// Called when streaming animation completes
  VoidCallback? onStreamingComplete;
}

/// Riverpod provider for markdown hooks
final markdownHooksProvider = Provider<MarkdownHooks>((ref) {
  return MarkdownHooks();
});
```

### 2. `lib/core/services/image_load_tracker.dart`

Per-message image tracking:

```dart
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'markdown_hooks.dart';

/// Tracks image loading state per message
class ImageLoadTracker extends ChangeNotifier {
  /// messageId → {imageUrl → ImageLoadState}
  final Map<String, Map<String, ImageLoadState>> _tracking = {};

  /// Callback when all images in a message are loaded
  AllImagesLoadedCallback? onAllImagesLoaded;

  /// Callback when individual image state changes
  ImageLoadCallback? onImageLoad;

  /// Start tracking an image for a message
  void trackImage(String messageId, String imageUrl) {
    _tracking.putIfAbsent(messageId, () => {});
    if (!_tracking[messageId]!.containsKey(imageUrl)) {
      _tracking[messageId]![imageUrl] = ImageLoadState.loading;
      onImageLoad?.call(imageUrl, messageId, ImageLoadState.loading);
      notifyListeners();
    }
  }

  /// Mark an image as loaded
  void markLoaded(String messageId, String imageUrl) {
    if (_tracking[messageId]?.containsKey(imageUrl) == true) {
      _tracking[messageId]![imageUrl] = ImageLoadState.loaded;
      onImageLoad?.call(imageUrl, messageId, ImageLoadState.loaded);
      notifyListeners();
      _checkAllImagesLoaded(messageId);
    }
  }

  /// Mark an image as errored
  void markError(String messageId, String imageUrl) {
    if (_tracking[messageId]?.containsKey(imageUrl) == true) {
      _tracking[messageId]![imageUrl] = ImageLoadState.error;
      onImageLoad?.call(imageUrl, messageId, ImageLoadState.error);
      notifyListeners();
      _checkAllImagesLoaded(messageId);
    }
  }

  /// Check if all images for a message are loaded (or errored)
  bool areAllImagesLoaded(String messageId) {
    final images = _tracking[messageId];
    if (images == null || images.isEmpty) return true;
    return images.values.every(
      (state) => state == ImageLoadState.loaded || state == ImageLoadState.error,
    );
  }

  /// Get loading state for a specific image
  ImageLoadState? getImageState(String messageId, String imageUrl) {
    return _tracking[messageId]?[imageUrl];
  }

  /// Clear tracking for a message
  void clearMessage(String messageId) {
    _tracking.remove(messageId);
    notifyListeners();
  }

  void _checkAllImagesLoaded(String messageId) {
    if (areAllImagesLoaded(messageId)) {
      onAllImagesLoaded?.call(messageId);
    }
  }
}

/// Riverpod provider for image load tracker
final imageLoadTrackerProvider = ChangeNotifierProvider<ImageLoadTracker>((ref) {
  final hooks = ref.watch(markdownHooksProvider);
  final tracker = ImageLoadTracker();
  tracker.onAllImagesLoaded = hooks.onAllImagesLoaded;
  tracker.onImageLoad = hooks.onImageLoad;
  return tracker;
});
```

### 3. `lib/features/chat/widgets/tracked_markdown_image.dart`

Image widget with load tracking:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../core/services/image_load_tracker.dart';

/// Image widget that tracks loading state for markdown images
class TrackedMarkdownImage extends ConsumerStatefulWidget {
  final String imageUrl;
  final String messageId;
  final double? width;
  final double? height;

  const TrackedMarkdownImage({
    super.key,
    required this.imageUrl,
    required this.messageId,
    this.width,
    this.height,
  });

  @override
  ConsumerState<TrackedMarkdownImage> createState() => _TrackedMarkdownImageState();
}

class _TrackedMarkdownImageState extends ConsumerState<TrackedMarkdownImage> {
  @override
  void initState() {
    super.initState();
    // Register this image for tracking
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(imageLoadTrackerProvider).trackImage(
        widget.messageId,
        widget.imageUrl,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final tracker = ref.watch(imageLoadTrackerProvider);

    return CachedNetworkImage(
      imageUrl: widget.imageUrl,
      width: widget.width,
      height: widget.height,
      fit: BoxFit.contain,
      placeholder: (context, url) => Container(
        width: widget.width ?? 200,
        height: widget.height ?? 150,
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        child: const Center(
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      imageBuilder: (context, imageProvider) {
        // Mark as loaded when image is ready
        WidgetsBinding.instance.addPostFrameCallback((_) {
          tracker.markLoaded(widget.messageId, widget.imageUrl);
        });
        return Image(
          image: imageProvider,
          width: widget.width,
          height: widget.height,
          fit: BoxFit.contain,
        );
      },
      errorWidget: (context, url, error) {
        // Mark as error
        WidgetsBinding.instance.addPostFrameCallback((_) {
          tracker.markError(widget.messageId, widget.imageUrl);
        });
        return Container(
          width: widget.width ?? 200,
          height: widget.height ?? 100,
          color: Theme.of(context).colorScheme.errorContainer,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.broken_image_outlined,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 4),
              Text(
                'Failed to load image',
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
```

### 4. `lib/features/chat/widgets/markdown_code_block.dart`

Custom code block builder for flutter_markdown:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:markdown/markdown.dart' as md;

/// Custom code block builder for flutter_markdown with copy/quote support
class MarkdownCodeBlockBuilder extends MarkdownElementBuilder {
  final void Function(String code, String? language)? onCopy;
  final void Function(String quotedText)? onQuote;
  final String? messageId;

  MarkdownCodeBlockBuilder({
    this.onCopy,
    this.onQuote,
    this.messageId,
  });

  @override
  Widget? visitElementAfter(md.Element element, TextStyle? preferredStyle) {
    // Extract language from info string (e.g., ```dart)
    String? language;
    if (element.attributes['class'] != null) {
      final classes = element.attributes['class']!.split(' ');
      for (final cls in classes) {
        if (cls.startsWith('language-')) {
          language = cls.substring('language-'.length);
          break;
        }
      }
    }

    final code = element.textContent.trim();

    return _StyledCodeBlock(
      code: code,
      language: language,
      onCopy: onCopy,
      onQuote: onQuote,
    );
  }
}

/// Styled code block widget with copy button
class _StyledCodeBlock extends StatefulWidget {
  final String code;
  final String? language;
  final void Function(String code, String? language)? onCopy;
  final void Function(String quotedText)? onQuote;

  const _StyledCodeBlock({
    required this.code,
    this.language,
    this.onCopy,
    this.onQuote,
  });

  @override
  State<_StyledCodeBlock> createState() => _StyledCodeBlockState();
}

class _StyledCodeBlockState extends State<_StyledCodeBlock> {
  bool _copied = false;

  Future<void> _copyCode() async {
    await Clipboard.setData(ClipboardData(text: widget.code));
    widget.onCopy?.call(widget.code, widget.language);
    setState(() => _copied = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header with language and copy button
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHigh,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(7)),
            ),
            child: Row(
              children: [
                if (widget.language?.isNotEmpty == true)
                  Text(
                    widget.language!,
                    style: TextStyle(
                      fontSize: 12,
                      color: colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                const Spacer(),
                InkWell(
                  onTap: _copyCode,
                  borderRadius: BorderRadius.circular(4),
                  child: Padding(
                    padding: const EdgeInsets.all(4),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _copied ? Icons.check : Icons.copy_outlined,
                          size: 14,
                          color: _copied ? Colors.green : colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          _copied ? 'Copied!' : 'Copy',
                          style: TextStyle(
                            fontSize: 12,
                            color: _copied ? Colors.green : colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          // Code content with selection and quote
          Padding(
            padding: const EdgeInsets.all(12),
            child: SelectableText(
              widget.code,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                color: colorScheme.onSurface,
              ),
              contextMenuBuilder: widget.onQuote != null
                  ? (context, editableTextState) {
                      final selection = editableTextState.textEditingValue.selection;
                      final selectedText = selection.textInside(widget.code);

                      return AdaptiveTextSelectionToolbar(
                        anchors: editableTextState.contextMenuAnchors,
                        children: [
                          TextSelectionToolbarTextButton(
                            padding: const EdgeInsets.all(8),
                            onPressed: () {
                              Clipboard.setData(ClipboardData(text: selectedText));
                              editableTextState.hideToolbar();
                            },
                            child: const Text('Copy'),
                          ),
                          if (selectedText.isNotEmpty)
                            TextSelectionToolbarTextButton(
                              padding: const EdgeInsets.all(8),
                              onPressed: () {
                                final quoted = selectedText
                                    .split('\n')
                                    .map((line) => '> $line')
                                    .join('\n');
                                widget.onQuote!(quoted);
                                editableTextState.hideToolbar();
                              },
                              child: const Text('Quote'),
                            ),
                        ],
                      );
                    }
                  : null,
            ),
          ),
        ],
      ),
    );
  }
}
```

### 5. `lib/features/chat/widgets/streaming_markdown_widget.dart`

Main wrapper widget:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_streaming_text_markdown/flutter_streaming_text_markdown.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/services/markdown_hooks.dart';
import '../../../core/services/image_load_tracker.dart';
import 'tracked_markdown_image.dart';
import 'markdown_code_block.dart';

/// Widget that renders markdown with streaming animation support
///
/// - During streaming: Uses StreamingTextMarkdown.claude() for animation
/// - After finalization: Uses MarkdownBody with full callbacks
class StreamingMarkdownWidget extends ConsumerStatefulWidget {
  final String text;
  final String messageId;
  final bool isStreaming;
  final TextStyle? textStyle;
  final void Function(String quotedText)? onQuote;

  const StreamingMarkdownWidget({
    super.key,
    required this.text,
    required this.messageId,
    required this.isStreaming,
    this.textStyle,
    this.onQuote,
  });

  @override
  ConsumerState<StreamingMarkdownWidget> createState() => _StreamingMarkdownWidgetState();
}

class _StreamingMarkdownWidgetState extends ConsumerState<StreamingMarkdownWidget> {
  late StreamingTextController _controller;

  @override
  void initState() {
    super.initState();
    _controller = StreamingTextController();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final hooks = ref.watch(markdownHooksProvider);
    final colorScheme = Theme.of(context).colorScheme;

    if (widget.isStreaming) {
      // Streaming mode - use animated markdown
      return StreamingTextMarkdown.claude(
        text: widget.text,
        controller: _controller,
        onComplete: () {
          hooks.onStreamingComplete?.call();
        },
        theme: StreamingTextTheme(
          textStyle: widget.textStyle ?? TextStyle(
            color: colorScheme.onSurface,
            fontSize: 14,
          ),
        ),
      );
    } else {
      // Finalized mode - use static markdown with full callbacks
      return _buildStaticMarkdown(context, hooks);
    }
  }

  Widget _buildStaticMarkdown(BuildContext context, MarkdownHooks hooks) {
    final colorScheme = Theme.of(context).colorScheme;

    return MarkdownBody(
      data: widget.text,
      selectable: true,
      styleSheet: MarkdownStyleSheet(
        p: widget.textStyle ?? TextStyle(
          color: colorScheme.onSurface,
          fontSize: 14,
        ),
        code: TextStyle(
          fontFamily: 'monospace',
          fontSize: 13,
          color: colorScheme.onSurface,
          backgroundColor: colorScheme.surfaceContainerHighest,
        ),
        codeblockDecoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      onTapLink: (text, href, title) {
        hooks.onLinkTap?.call(href, text, widget.messageId);
        // Default behavior: open in browser
        if (href != null) {
          launchUrl(Uri.parse(href), mode: LaunchMode.externalApplication);
        }
      },
      imageBuilder: (uri, title, alt) {
        return TrackedMarkdownImage(
          imageUrl: uri.toString(),
          messageId: widget.messageId,
        );
      },
      builders: {
        'pre': MarkdownCodeBlockBuilder(
          onCopy: (code, language) {
            hooks.onCodeCopy?.call(code, language, widget.messageId);
          },
          onQuote: widget.onQuote != null
              ? (quotedText) {
                  hooks.onQuote?.call(quotedText, widget.messageId);
                  widget.onQuote?.call(quotedText);
                }
              : null,
          messageId: widget.messageId,
        ),
      },
    );
  }
}
```

---

## Files to Modify

### 1. `pubspec.yaml`

Add dependencies:

```yaml
dependencies:
  # ... existing deps ...

  # Streaming Markdown
  flutter_streaming_text_markdown: ^1.0.0  # Check latest version
  flutter_markdown: ^0.7.0  # May already be transitive
  url_launcher: ^6.2.0
```

### 2. `lib/features/chat/chat_content.dart`

**Location**: `messageTextBuilder` callback (around lines 915-988)

**Before**:
```dart
final textWidget = MessageTextWithCodeBlocks(
  text: message.text,
  textStyle: textStyle,
  onQuote: (quotedText) {
    // Insert quoted text into input
    final currentText = _textController.text;
    final newText = currentText.isEmpty
        ? '$quotedText\n\n'
        : '$currentText\n\n$quotedText\n\n';
    _textController.text = newText;
    _textController.selection = TextSelection.collapsed(
      offset: newText.length,
    );
  },
);
```

**After**:
```dart
final textWidget = StreamingMarkdownWidget(
  text: message.text,
  messageId: chatMessage?.id ?? message.createdAt.toString(),
  isStreaming: chatMessage?.isStreaming ?? false,
  textStyle: textStyle,
  onQuote: (quotedText) {
    // Insert quoted text into input
    final currentText = _textController.text;
    final newText = currentText.isEmpty
        ? '$quotedText\n\n'
        : '$currentText\n\n$quotedText\n\n';
    _textController.text = newText;
    _textController.selection = TextSelection.collapsed(
      offset: newText.length,
    );
  },
);
```

**Import to add**:
```dart
import 'widgets/streaming_markdown_widget.dart';
```

### 3. `lib/features/chat/chat_screen.dart`

Initialize hooks with default behaviors in build() or via a provider setup:

```dart
// Near the top of build() method or in a dedicated setup
final hooks = ref.read(markdownHooksProvider);

// Default link handling (open in browser)
hooks.onLinkTap ??= (href, text, messageId) {
  if (href != null) {
    launchUrl(Uri.parse(href), mode: LaunchMode.externalApplication);
  }
};

// Optional: Log image loads for debugging
hooks.onImageLoad ??= (imageUrl, messageId, state) {
  debugPrint('Image $imageUrl in message $messageId: $state');
};

// Optional: Handle all-images-loaded (useful for auto-scroll)
hooks.onAllImagesLoaded ??= (messageId) {
  debugPrint('All images loaded for message $messageId');
};
```

---

## Hook Usage Examples

### Custom Link Handling

```dart
// Intercept internal links
hooks.onLinkTap = (href, text, messageId) {
  if (href?.startsWith('internal://') == true) {
    // Handle internally - navigate to app route
    Navigator.pushNamed(context, href!.replaceFirst('internal://', '/'));
  } else if (href?.startsWith('mailto:') == true) {
    // Handle email links
    launchUrl(Uri.parse(href!));
  } else {
    // Default: open in browser
    launchUrl(Uri.parse(href!), mode: LaunchMode.externalApplication);
  }
};
```

### Track All Images Loaded (for Auto-Scroll)

```dart
hooks.onAllImagesLoaded = (messageId) {
  // Safe to scroll to bottom now that all images are loaded
  // Images won't cause layout shifts
  WidgetsBinding.instance.addPostFrameCallback((_) {
    scrollController.animateTo(
      scrollController.position.maxScrollExtent,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOut,
    );
  });
};
```

### Analytics on Image Loads

```dart
hooks.onImageLoad = (imageUrl, messageId, state) {
  analytics.track('markdown_image_load', {
    'url': imageUrl,
    'messageId': messageId,
    'state': state.name,
    'timestamp': DateTime.now().toIso8601String(),
  });
};
```

### Code Copy Analytics

```dart
hooks.onCodeCopy = (code, language, messageId) {
  analytics.track('code_copied', {
    'language': language ?? 'unknown',
    'messageId': messageId,
    'codeLength': code.length,
  });
};
```

---

## Migration Strategy

### Phase 1: Infrastructure (non-breaking)
1. Add package dependencies to pubspec.yaml
2. Create `markdown_hooks.dart` with types and provider
3. Create `image_load_tracker.dart` service
4. Create `tracked_markdown_image.dart` widget
5. Create `markdown_code_block.dart` builder

### Phase 2: Widget Implementation
1. Create `streaming_markdown_widget.dart`
2. Wire up hooks to url_launcher for links
3. Connect image tracking to callbacks
4. Preserve code block styling + copy/quote features

### Phase 3: Integration
1. Update `messageTextBuilder` in `chat_content.dart`
2. Initialize default hook behaviors in `chat_screen.dart`
3. Test streaming → finalized transition

### Phase 4: Cleanup
1. Remove or deprecate `MessageTextWithCodeBlocks` from `code_block_widget.dart`
2. Update APP_FEATURES.md

---

## Critical Files Reference

| File | Purpose |
|------|---------|
| `lib/features/chat/chat_content.dart` | Main integration point (lines 915-988) |
| `lib/features/chat/widgets/code_block_widget.dart` | Current impl to replace/reference |
| `lib/core/services/chat_service.dart` | ChatNotifier with `isStreaming` state |
| `lib/features/chat/builders/message_builder.dart` | Message conversion layer |

---

## Testing Checklist

- [ ] Streaming text animates with Claude-style
- [ ] Links open in browser when tapped
- [ ] Images fire callbacks on load/error
- [ ] All-images-loaded fires when message images complete
- [ ] Code blocks have copy button with feedback
- [ ] Quote context menu works on selected text
- [ ] Transition from streaming → static is seamless
- [ ] Concurrent streaming messages work correctly

---

## Dependencies

```yaml
# New dependencies to add
flutter_streaming_text_markdown: ^1.0.0
flutter_markdown: ^0.7.0
url_launcher: ^6.2.0

# Already present (used by new widgets)
cached_network_image: ^3.4.1  # For TrackedMarkdownImage
flutter_riverpod: ^2.6.1      # For providers
```
