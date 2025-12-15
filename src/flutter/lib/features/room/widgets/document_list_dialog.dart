import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// ignore: unused_import // reason: required for model type
import 'package:soliplex/core/models/document_model.dart';
import 'package:soliplex/features/room/providers/document_providers.dart';

class DocumentListDialog extends ConsumerWidget {
  const DocumentListDialog({required this.roomId, super.key});

  final String roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final documentsAsync = ref.watch(roomDocumentsProvider(roomId));

    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600, maxHeight: 400),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Documents for Room "$roomId"',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 16),
              documentsAsync.when(
                data: (documents) {
                  if (documents.isEmpty) {
                    return const Expanded(
                      child: Center(
                        child: Text('No documents found for this room.'),
                      ),
                    );
                  }
                  return Expanded(
                    child: ListView.builder(
                      itemCount: documents.length,
                      itemBuilder: (context, index) {
                        final document = documents[index];
                        return ListTile(
                          title: Text(document.title),
                          subtitle: Text(
                            'Size: ${document.size ?? 'N/A'} bytes, '
                            'Type: ${document.contentType ?? 'N/A'}',
                          ),
                          onTap: () {
                            // TODO(dev): Implement document viewing/downloading // ignore: lines_longer_than_80_chars
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Tapped on ${document.title}'),
                              ),
                            );
                          },
                        );
                      },
                    ),
                  );
                },
                loading: () => const Expanded(
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (error, stack) => Expanded(
                  child: Center(
                    child: Text('Error loading documents: $error'),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Align(
                alignment: Alignment.bottomRight,
                child: TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
