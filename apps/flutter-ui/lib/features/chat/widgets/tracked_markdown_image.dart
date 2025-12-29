import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/services/image_load_tracker.dart';

/// Image widget that tracks loading state for markdown images.
///
/// This widget wraps CachedNetworkImage and automatically registers
/// with the ImageLoadTracker to track loading progress and completion.
///
/// When the image loads or errors, the tracker is notified, which in turn
/// fires the appropriate callbacks in MarkdownHooks.
class TrackedMarkdownImage extends ConsumerStatefulWidget {
  const TrackedMarkdownImage({
    required this.imageUrl,
    required this.messageId,
    super.key,
    this.width,
    this.height,
  });

  /// The URL of the image to load
  final String imageUrl;

  /// The ID of the message containing this image
  final String messageId;

  /// Optional fixed width
  final double? width;

  /// Optional fixed height
  final double? height;

  @override
  ConsumerState<TrackedMarkdownImage> createState() =>
      _TrackedMarkdownImageState();
}

class _TrackedMarkdownImageState extends ConsumerState<TrackedMarkdownImage> {
  bool _registered = false;
  bool _completed = false;

  @override
  void initState() {
    super.initState();
    // Register this image for tracking after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !_registered) {
        _registered = true;
        ref
            .read(imageLoadTrackerProvider.notifier)
            .trackImage(widget.messageId, widget.imageUrl);
      }
    });
  }

  void _markLoaded() {
    if (!_completed && mounted) {
      _completed = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          ref
              .read(imageLoadTrackerProvider.notifier)
              .markLoaded(widget.messageId, widget.imageUrl);
        }
      });
    }
  }

  void _markError() {
    if (!_completed && mounted) {
      _completed = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          ref
              .read(imageLoadTrackerProvider.notifier)
              .markError(widget.messageId, widget.imageUrl);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return CachedNetworkImage(
      imageUrl: widget.imageUrl,
      width: widget.width,
      height: widget.height,
      fit: BoxFit.contain,
      placeholder: (context, url) => Container(
        width: widget.width ?? 200,
        height: widget.height ?? 150,
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
      ),
      imageBuilder: (context, imageProvider) {
        // Mark as loaded when image is ready
        _markLoaded();
        return ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Image(
            image: imageProvider,
            width: widget.width,
            height: widget.height,
            fit: BoxFit.contain,
          ),
        );
      },
      errorWidget: (context, url, error) {
        // Mark as error
        _markError();
        return Container(
          width: widget.width ?? 200,
          height: widget.height ?? 100,
          decoration: BoxDecoration(
            color: colorScheme.errorContainer,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.broken_image_outlined,
                color: colorScheme.error,
                size: 32,
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  'Failed to load image',
                  style: TextStyle(fontSize: 12, color: colorScheme.error),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
