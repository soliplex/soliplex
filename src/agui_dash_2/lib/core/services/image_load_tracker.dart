import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'markdown_hooks.dart';

/// Tracks image loading state per message.
///
/// This service maintains a map of message IDs to their images and loading states.
/// It fires callbacks when individual images complete and when all images in a
/// message are loaded.
///
/// Example usage:
/// ```dart
/// final tracker = ref.read(imageLoadTrackerProvider);
/// tracker.trackImage('msg-123', 'https://example.com/image.png');
/// // Later, when image loads:
/// tracker.markLoaded('msg-123', 'https://example.com/image.png');
/// ```
class ImageLoadTracker extends ChangeNotifier {
  /// messageId -> {imageUrl -> ImageLoadState}
  final Map<String, Map<String, ImageLoadState>> _tracking = {};

  /// Callback when all images in a message are loaded
  AllImagesLoadedCallback? onAllImagesLoaded;

  /// Callback when individual image state changes
  ImageLoadCallback? onImageLoad;

  /// Start tracking an image for a message.
  ///
  /// If the image is already being tracked, this is a no-op.
  void trackImage(String messageId, String imageUrl) {
    _tracking.putIfAbsent(messageId, () => {});
    if (!_tracking[messageId]!.containsKey(imageUrl)) {
      _tracking[messageId]![imageUrl] = ImageLoadState.loading;
      onImageLoad?.call(imageUrl, messageId, ImageLoadState.loading);
      notifyListeners();
    }
  }

  /// Mark an image as successfully loaded.
  void markLoaded(String messageId, String imageUrl) {
    if (_tracking[messageId]?.containsKey(imageUrl) == true) {
      _tracking[messageId]![imageUrl] = ImageLoadState.loaded;
      onImageLoad?.call(imageUrl, messageId, ImageLoadState.loaded);
      notifyListeners();
      _checkAllImagesLoaded(messageId);
    }
  }

  /// Mark an image as failed to load.
  void markError(String messageId, String imageUrl) {
    if (_tracking[messageId]?.containsKey(imageUrl) == true) {
      _tracking[messageId]![imageUrl] = ImageLoadState.error;
      onImageLoad?.call(imageUrl, messageId, ImageLoadState.error);
      notifyListeners();
      _checkAllImagesLoaded(messageId);
    }
  }

  /// Check if all images for a message are loaded (or errored).
  ///
  /// Returns true if there are no images tracked for this message,
  /// or if all tracked images have completed (loaded or errored).
  bool areAllImagesLoaded(String messageId) {
    final images = _tracking[messageId];
    if (images == null || images.isEmpty) return true;
    return images.values.every(
      (state) => state == ImageLoadState.loaded || state == ImageLoadState.error,
    );
  }

  /// Get the current count of images in each state for a message.
  Map<ImageLoadState, int> getImageStateCounts(String messageId) {
    final images = _tracking[messageId];
    if (images == null) return {};

    final counts = <ImageLoadState, int>{};
    for (final state in images.values) {
      counts[state] = (counts[state] ?? 0) + 1;
    }
    return counts;
  }

  /// Get loading state for a specific image.
  ImageLoadState? getImageState(String messageId, String imageUrl) {
    return _tracking[messageId]?[imageUrl];
  }

  /// Clear tracking for a message.
  ///
  /// Call this when a message is removed from the chat.
  void clearMessage(String messageId) {
    _tracking.remove(messageId);
    notifyListeners();
  }

  /// Clear all tracking data.
  void clearAll() {
    _tracking.clear();
    notifyListeners();
  }

  void _checkAllImagesLoaded(String messageId) {
    if (areAllImagesLoaded(messageId)) {
      onAllImagesLoaded?.call(messageId);
    }
  }
}

/// Riverpod provider for image load tracker.
///
/// This automatically wires up the tracker's callbacks to the
/// [markdownHooksProvider] so that hook consumers receive image events.
final imageLoadTrackerProvider = ChangeNotifierProvider<ImageLoadTracker>((ref) {
  final hooks = ref.watch(markdownHooksProvider);
  final tracker = ImageLoadTracker();

  // Wire up callbacks from hooks
  tracker.onAllImagesLoaded = hooks.onAllImagesLoaded;
  tracker.onImageLoad = hooks.onImageLoad;

  return tracker;
});
