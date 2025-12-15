import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/services/markdown_hooks.dart';

/// Immutable state for image loading tracking.
@immutable
class ImageLoadTrackerState {
  const ImageLoadTrackerState({this.tracking = const {}});

  /// messageId -> {imageUrl -> ImageLoadState}
  final Map<String, Map<String, ImageLoadState>> tracking;

  /// Create a copy with updated tracking data.
  ImageLoadTrackerState copyWith({
    Map<String, Map<String, ImageLoadState>>? tracking,
  }) {
    return ImageLoadTrackerState(tracking: tracking ?? this.tracking);
  }

  /// Check if all images for a message are loaded (or errored).
  bool areAllImagesLoaded(String messageId) {
    final images = tracking[messageId];
    if (images == null || images.isEmpty) return true;
    return images.values.every(
      (state) =>
          state == ImageLoadState.loaded || state == ImageLoadState.error,
    );
  }

  /// Get the current count of images in each state for a message.
  Map<ImageLoadState, int> getImageStateCounts(String messageId) {
    final images = tracking[messageId];
    if (images == null) return {};

    final counts = <ImageLoadState, int>{};
    for (final state in images.values) {
      counts[state] = (counts[state] ?? 0) + 1;
    }
    return counts;
  }

  /// Get loading state for a specific image.
  ImageLoadState? getImageState(String messageId, String imageUrl) {
    return tracking[messageId]?[imageUrl];
  }
}

/// Tracks image loading state per message.
///
/// This service maintains a map of message IDs to their images and loading
/// states.
/// It fires callbacks when individual images complete and when all images in a
/// message are loaded.
///
/// Example usage:
/// ```dart
/// final tracker = ref.read(imageLoadTrackerProvider.notifier);
/// tracker.trackImage('msg-123', 'https://example.com/image.png');
/// // Later, when image loads:
/// tracker.markLoaded('msg-123', 'https://example.com/image.png');
/// ```
class ImageLoadTracker extends StateNotifier<ImageLoadTrackerState> {
  ImageLoadTracker() : super(const ImageLoadTrackerState());

  /// Callback when all images in a message are loaded
  AllImagesLoadedCallback? onAllImagesLoaded;

  /// Callback when individual image state changes
  ImageLoadCallback? onImageLoad;

  /// Start tracking an image for a message.
  ///
  /// If the image is already being tracked, this is a no-op.
  void trackImage(String messageId, String imageUrl) {
    final currentImages = state.tracking[messageId] ?? {};
    if (currentImages.containsKey(imageUrl)) return;

    // Create new immutable state
    final newImages = Map<String, ImageLoadState>.from(currentImages);
    newImages[imageUrl] = ImageLoadState.loading;

    final newTracking = Map<String, Map<String, ImageLoadState>>.from(
      state.tracking,
    );
    newTracking[messageId] = newImages;

    state = state.copyWith(tracking: newTracking);
    onImageLoad?.call(imageUrl, messageId, ImageLoadState.loading);
  }

  /// Mark an image as successfully loaded.
  void markLoaded(String messageId, String imageUrl) {
    _updateImageState(messageId, imageUrl, ImageLoadState.loaded);
  }

  /// Mark an image as failed to load.
  void markError(String messageId, String imageUrl) {
    _updateImageState(messageId, imageUrl, ImageLoadState.error);
  }

  void _updateImageState(
    String messageId,
    String imageUrl,
    ImageLoadState newState,
  ) {
    final currentImages = state.tracking[messageId];
    if (currentImages == null || !currentImages.containsKey(imageUrl)) return;

    // Create new immutable state
    final newImages = Map<String, ImageLoadState>.from(currentImages);
    newImages[imageUrl] = newState;

    final newTracking = Map<String, Map<String, ImageLoadState>>.from(
      state.tracking,
    );
    newTracking[messageId] = newImages;

    state = state.copyWith(tracking: newTracking);
    onImageLoad?.call(imageUrl, messageId, newState);
    _checkAllImagesLoaded(messageId);
  }

  /// Check if all images for a message are loaded (or errored).
  bool areAllImagesLoaded(String messageId) =>
      state.areAllImagesLoaded(messageId);

  /// Get the current count of images in each state for a message.
  Map<ImageLoadState, int> getImageStateCounts(String messageId) =>
      state.getImageStateCounts(messageId);

  /// Get loading state for a specific image.
  ImageLoadState? getImageState(String messageId, String imageUrl) =>
      state.getImageState(messageId, imageUrl);

  /// Clear tracking for a message.
  ///
  /// Call this when a message is removed from the chat.
  void clearMessage(String messageId) {
    if (!state.tracking.containsKey(messageId)) return;

    final newTracking = Map<String, Map<String, ImageLoadState>>.from(
      state.tracking,
    );
    newTracking.remove(messageId);
    state = state.copyWith(tracking: newTracking);
  }

  /// Clear all tracking data.
  void clearAll() {
    if (state.tracking.isEmpty) return;
    state = const ImageLoadTrackerState();
  }

  void _checkAllImagesLoaded(String messageId) {
    if (state.areAllImagesLoaded(messageId)) {
      onAllImagesLoaded?.call(messageId);
    }
  }
}

/// Riverpod provider for image load tracker.
///
/// This automatically wires up the tracker's callbacks to the
/// markdownHooksProvider so that hook consumers receive image events.
final imageLoadTrackerProvider =
    StateNotifierProvider<ImageLoadTracker, ImageLoadTrackerState>((ref) {
      final hooks = ref.watch(markdownHooksProvider);
      final tracker = ImageLoadTracker();

      // Wire up callbacks from hooks
      tracker.onAllImagesLoaded = hooks.onAllImagesLoaded;
      tracker.onImageLoad = hooks.onImageLoad;

      return tracker;
    });
