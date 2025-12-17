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
  bool _isLoading = false;
  Uint8List? _imageData;
  String? _error;
  bool _isConfigured = false;
  bool _checkedStatus = false;

  @override
  void initState() {
    super.initState();
    _checkStatus();
  }

  Future<void> _checkStatus() async {
    final connectionManager = ref.read(connectionManagerProvider);
    if (!connectionManager.isConfigured) return;

    final urlBuilder = UrlBuilder(connectionManager.serverUrl);
    final uri = Uri.parse(
      '${urlBuilder.apiBaseUrl}/rooms/${widget.room.id}/bg_image',
    );

    try {
      final response = await connectionManager.head(uri);
      if (mounted) {
        setState(() {
          _isConfigured = response.statusCode == 200;
          _checkedStatus = true;
        });
      }
    } on Object catch (_) {
      if (mounted) {
        setState(() {
          _isConfigured = false;
          _checkedStatus = true;
        });
      }
    }
  }

  Future<void> _fetchImage() async {
    if (_imageData != null) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final connectionManager = ref.read(connectionManagerProvider);
      if (!connectionManager.isConfigured) {
        throw Exception('No active server');
      }

      final urlBuilder = UrlBuilder(connectionManager.serverUrl);
      final uri = Uri.parse(
        '${urlBuilder.apiBaseUrl}/rooms/${widget.room.id}/bg_image',
      );

      final response = await connectionManager.get(uri);
      if (response.statusCode == 200) {
        if (mounted) {
          setState(() {
            _imageData = response.bodyBytes;
            _isLoading = false;
          });
        }
      } else {
        throw Exception('Failed to load image: ${response.statusCode}');
      }
    } on Object catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
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
              childrenPadding: const EdgeInsets.all(16),
              onExpansionChanged: (expanded) {
                if (expanded && _isConfigured && _imageData == null) {
                  _fetchImage();
                }
              },
              children: [
                if (!_isConfigured)
                  Text(
                    'No background image set for this room.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  )
                else if (_isLoading)
                  const Center(child: CircularProgressIndicator())
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
                      fit: BoxFit.cover,
                      width: double.infinity,
                      height: 150,
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
