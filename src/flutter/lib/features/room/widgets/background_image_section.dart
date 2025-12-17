import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/room_models.dart';
import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/utils/url_builder.dart';

class BackgroundImageSection extends ConsumerStatefulWidget {
  const BackgroundImageSection({required this.room, super.key});
  final Room room;

  @override
  ConsumerState<BackgroundImageSection> createState() =>
      _BackgroundImageSectionState();
}

class _BackgroundImageSectionState
    extends ConsumerState<BackgroundImageSection> {
  Uint8List? _imageData;
  String? _error;
  bool _isConfigured = false;
  bool _checkedStatus = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _loadBackgroundImage();
      }
    });
  }

  Future<void> _loadBackgroundImage() async {
    final connectionManager = ref.read(connectionManagerProvider);
    if (!connectionManager.isConfigured) return;

    final urlBuilder = UrlBuilder(connectionManager.serverUrl);
    final uri = Uri.parse(
      '${urlBuilder.apiBaseUrl}/rooms/${widget.room.id}/bg_image',
    );

    try {
      final response = await connectionManager.get(uri);

      if (mounted) {
        setState(() {
          _isConfigured = response.statusCode == 200;
          if (_isConfigured) {
            _imageData = response.bodyBytes;
          }
          _checkedStatus = true;
        });
      }
    } on Object catch (e) {
      if (mounted) {
        setState(() {
          _isConfigured = false;
          _error = e.toString();
          _checkedStatus = true;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_checkedStatus) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'BACKGROUND IMAGE',
          style: theme.textTheme.labelSmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: colorScheme.outline.withValues(alpha: 0.1),
            ),
          ),
          child: Theme(
            data: theme.copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              title: Text(
                'Room Background',
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
              subtitle: Text(
                _isConfigured ? 'Configured' : 'Not configured',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: _isConfigured
                      ? Colors.green
                      : colorScheme.onSurfaceVariant,
                ),
              ),
              leading: Icon(
                Icons.image_outlined,
                color: colorScheme.onSurfaceVariant,
              ),
              childrenPadding: const EdgeInsets.all(12),
              children: [
                if (!_isConfigured)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      'No background image set for this room.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  )
                else if (_error != null)
                  Text(
                    'Error loading image',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.error,
                    ),
                  )
                else if (_imageData != null)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.memory(
                      _imageData!,
                      fit: BoxFit.contain,
                      width: double.infinity,
                      height: 400,
                      errorBuilder: (context, error, stackTrace) {
                        return Container(
                          height: 200,
                          width: double.infinity,
                          color: colorScheme.errorContainer,
                          child: Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.broken_image,
                                  color: colorScheme.error,
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Failed to render image',
                                  style: TextStyle(color: colorScheme.error),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
