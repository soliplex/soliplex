import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/utils/url_builder.dart';

/// Collapsible citations section that appears below message content.
///
/// Shows RAG citations in an expandable section. Individual citations
/// can also be tapped to expand their content preview. Page badges can
/// be tapped to show chunk visualization from the server.
class CollapsibleCitationsWidget extends ConsumerStatefulWidget {
  const CollapsibleCitationsWidget({
    required this.citations,
    required this.isExpanded,
    required this.onToggle,
    required this.roomId,
    super.key,
  });

  /// The list of citations to display
  final List<Citation> citations;

  /// Whether the section is expanded
  final bool isExpanded;

  /// Callback when expand/collapse is toggled
  final VoidCallback onToggle;

  /// Room ID for fetching chunk visualizations
  final String roomId;

  @override
  ConsumerState<CollapsibleCitationsWidget> createState() =>
      _CollapsibleCitationsWidgetState();
}

class _CollapsibleCitationsWidgetState
    extends ConsumerState<CollapsibleCitationsWidget> {
  /// Track which individual citations are expanded (by index)
  final Set<int> _expandedCitations = {};

  /// Fetch chunk visualization from the server and show in a dialog.
  void _showChunkVisualization(
    BuildContext context,
    Citation citation,
  ) {
    final urlBuilder = ref.read(urlBuilderProvider);
    if (urlBuilder == null) return;

    final uri = urlBuilder.roomChunk(widget.roomId, citation.chunkId);

    // Show dialog with loading state that transitions to images
    showDialog<void>(
      context: context,
      builder: (dialogContext) => _ChunkVisualizationDialog(
        uri: uri,
        citation: citation,
        onShowFullImage: (imageBase64, pageNumber, totalPages) {
          _showFullImage(
            dialogContext,
            imageBase64,
            pageNumber,
            totalPages,
            citation.displayTitle,
          );
        },
      ),
    );
  }

  /// Show a full-size image in a dialog.
  void _showFullImage(
    BuildContext context,
    String imageBase64,
    int pageNumber,
    int totalPages,
    String title,
  ) {
    final colorScheme = Theme.of(context).colorScheme;

    showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: colorScheme.surface,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(12),
                ),
              ),
              child: Row(
                children: [
                  Text(
                    'Page $pageNumber of $totalPages',
                    style: TextStyle(
                      color: colorScheme.onSurface,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    title,
                    style: TextStyle(
                      color: colorScheme.onSurfaceVariant,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(width: 16),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                    color: colorScheme.onSurface,
                    iconSize: 20,
                  ),
                ],
              ),
            ),
            // Image
            Flexible(
              child: Container(
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerLow,
                  borderRadius: const BorderRadius.vertical(
                    bottom: Radius.circular(12),
                  ),
                ),
                child: InteractiveViewer(
                  minScale: 0.5,
                  maxScale: 4,
                  child: Image.memory(
                    base64Decode(imageBase64),
                    fit: BoxFit.contain,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.citations.isEmpty) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Container(
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: colorScheme.outlineVariant.withValues(alpha: 0.5),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header
            _buildHeader(context, colorScheme),

            // Content (when expanded)
            if (widget.isExpanded) _buildContent(context, colorScheme),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ColorScheme colorScheme) {
    final count = widget.citations.length;
    final label = count == 1 ? '1 citation' : '$count citations';

    // Check if this is stub data (for debugging)
    final isStub = widget.citations.any((c) => c.documentId == 'stub-doc-id');

    return InkWell(
      onTap: widget.onToggle,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            Icon(
              Icons.menu_book_outlined,
              size: 18,
              color: isStub ? Colors.orange : colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 8),

            // Label
            Expanded(
              child: Text(
                isStub ? '$label [STUB]' : label,
                style: TextStyle(
                  color: isStub ? Colors.orange : colorScheme.onSurfaceVariant,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),

            // Expand/collapse icon
            Icon(
              widget.isExpanded ? Icons.expand_less : Icons.expand_more,
              size: 20,
              color: isStub ? Colors.orange : colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, ColorScheme colorScheme) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          for (int i = 0; i < widget.citations.length; i++)
            _CitationRow(
              citation: widget.citations[i],
              isExpanded: _expandedCitations.contains(i),
              onToggle: () {
                setState(() {
                  if (_expandedCitations.contains(i)) {
                    _expandedCitations.remove(i);
                  } else {
                    _expandedCitations.add(i);
                  }
                });
              },
              onChunkTap: () =>
                  _showChunkVisualization(context, widget.citations[i]),
            ),
        ],
      ),
    );
  }
}

/// Individual citation row with expandable content.
class _CitationRow extends StatelessWidget {
  const _CitationRow({
    required this.citation,
    required this.isExpanded,
    required this.onToggle,
    required this.onChunkTap,
  });

  final Citation citation;
  final bool isExpanded;
  final VoidCallback onToggle;
  final VoidCallback onChunkTap;

  /// Check if citation is from a PDF file (supports chunk visualization).
  bool get _isPdfCitation =>
      citation.documentUri.toLowerCase().endsWith('.pdf');

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      margin: const EdgeInsets.only(top: 4),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Citation header (always visible)
          InkWell(
            onTap: onToggle,
            borderRadius: BorderRadius.circular(6),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Row(
                children: [
                  Icon(
                    Icons.description_outlined,
                    size: 16,
                    color: colorScheme.primary,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      citation.displayTitle,
                      style: TextStyle(
                        color: colorScheme.onSurface,
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  // Page numbers badge (tappable to show chunk visualization)
                  // Only show view button for PDF citations
                  if (_isPdfCitation &&
                      citation.formattedPageNumbers != null) ...[
                    const SizedBox(width: 8),
                    Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: onChunkTap,
                        borderRadius: BorderRadius.circular(4),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: colorScheme.primaryContainer,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                citation.formattedPageNumbers!,
                                style: TextStyle(
                                  color: colorScheme.onPrimaryContainer,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                              const SizedBox(width: 2),
                              Icon(
                                Icons.visibility_outlined,
                                size: 12,
                                color: colorScheme.onPrimaryContainer,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ] else if (_isPdfCitation) ...[
                    // Show view button for PDFs without page numbers
                    const SizedBox(width: 8),
                    Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: onChunkTap,
                        borderRadius: BorderRadius.circular(4),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: colorScheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Icon(
                            Icons.visibility_outlined,
                            size: 14,
                            color: colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(width: 4),
                  Icon(
                    isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 18,
                    color: colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),

          // Expanded content
          if (isExpanded) _buildExpandedContent(context, colorScheme),
        ],
      ),
    );
  }

  Widget _buildExpandedContent(BuildContext context, ColorScheme colorScheme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Headings (if available)
          if (citation.headings != null && citation.headings!.isNotEmpty) ...[
            Text(
              citation.headings!.join(' > '),
              style: TextStyle(
                color: colorScheme.onSurfaceVariant,
                fontSize: 10,
                fontStyle: FontStyle.italic,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 6),
          ],

          // Content preview - use SizedBox to force full width
          SizedBox(
            width: double.infinity,
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: colorScheme.surface,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(
                  color: colorScheme.outlineVariant.withValues(alpha: 0.3),
                ),
              ),
              constraints: const BoxConstraints(maxHeight: 150),
              child: SingleChildScrollView(
                child: Text(
                  citation.content,
                  style: TextStyle(
                    color: colorScheme.onSurfaceVariant,
                    fontSize: 11,
                    height: 1.4,
                  ),
                ),
              ),
            ),
          ),

          // Document URI (truncated)
          const SizedBox(height: 6),
          Text(
            citation.documentUri,
            style: TextStyle(
              color: colorScheme.outline,
              fontSize: 9,
              fontFamily: 'monospace',
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

/// Dialog that loads and displays chunk visualization images.
///
/// Handles loading state internally - no separate loading dialog needed.
class _ChunkVisualizationDialog extends StatefulWidget {
  const _ChunkVisualizationDialog({
    required this.uri,
    required this.citation,
    required this.onShowFullImage,
  });

  final Uri uri;
  final Citation citation;
  final void Function(String imageBase64, int pageNumber, int totalPages)
      onShowFullImage;

  @override
  State<_ChunkVisualizationDialog> createState() =>
      _ChunkVisualizationDialogState();
}

class _ChunkVisualizationDialogState extends State<_ChunkVisualizationDialog> {
  List<String>? _imagesBase64;
  String? _error;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadChunkImages();
  }

  Future<void> _loadChunkImages() async {
    try {
      final response = await http.get(widget.uri);
      if (!mounted) return;

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final images = (data['images_base_64'] as List<dynamic>?)
                ?.map((e) => e as String)
                .toList() ??
            [];

        if (images.isEmpty) {
          setState(() {
            _error = 'No page images available';
            _isLoading = false;
          });
        } else {
          setState(() {
            _imagesBase64 = images;
            _isLoading = false;
          });
        }
      } else {
        setState(() {
          _error = 'Failed to load: ${response.statusCode}';
          _isLoading = false;
        });
      }
    } on Object catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Error: $e';
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 700, maxHeight: 600),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.primaryContainer,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(28),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.image_outlined,
                    color: colorScheme.onPrimaryContainer,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.citation.displayTitle,
                          style: TextStyle(
                            color: colorScheme.onPrimaryContainer,
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (_imagesBase64 != null)
                          Text(
                            '${_imagesBase64!.length} '
                            'page${_imagesBase64!.length == 1 ? '' : 's'}',
                            style: TextStyle(
                              color: colorScheme.onPrimaryContainer
                                  .withValues(alpha: 0.7),
                              fontSize: 12,
                            ),
                          )
                        else if (_isLoading)
                          Text(
                            'Loading...',
                            style: TextStyle(
                              color: colorScheme.onPrimaryContainer
                                  .withValues(alpha: 0.7),
                              fontSize: 12,
                            ),
                          ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                    color: colorScheme.onPrimaryContainer,
                  ),
                ],
              ),
            ),
            // Content area
            Flexible(
              child: _buildContent(colorScheme),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(ColorScheme colorScheme) {
    if (_isLoading) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(48),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(color: colorScheme.primary),
              const SizedBox(height: 16),
              Text(
                'Loading chunk visualization...',
                style: TextStyle(color: colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(48),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                _error!,
                style: TextStyle(color: colorScheme.error),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        children: [
          for (var i = 0; i < _imagesBase64!.length; i++)
            _ChunkImageThumbnail(
              imageBase64: _imagesBase64![i],
              pageNumber: i + 1,
              onTap: () => widget.onShowFullImage(
                _imagesBase64![i],
                i + 1,
                _imagesBase64!.length,
              ),
            ),
        ],
      ),
    );
  }
}

/// Thumbnail widget for a chunk page image.
class _ChunkImageThumbnail extends StatelessWidget {
  const _ChunkImageThumbnail({
    required this.imageBase64,
    required this.pageNumber,
    required this.onTap,
  });

  final String imageBase64;
  final int pageNumber;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: 120,
          height: 160,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: colorScheme.outlineVariant,
            ),
          ),
          child: Stack(
            children: [
              // Image
              ClipRRect(
                borderRadius: BorderRadius.circular(7),
                child: Image.memory(
                  base64Decode(imageBase64),
                  width: 120,
                  height: 160,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) => ColoredBox(
                    color: colorScheme.surfaceContainerLow,
                    child: Center(
                      child: Icon(
                        Icons.broken_image_outlined,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ),
              ),
              // Page number badge
              Positioned(
                bottom: 4,
                right: 4,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: colorScheme.primaryContainer.withValues(alpha: 0.9),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'p.$pageNumber',
                    style: TextStyle(
                      color: colorScheme.onPrimaryContainer,
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
