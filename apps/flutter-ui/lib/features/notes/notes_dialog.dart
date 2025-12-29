import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/features/notes/notes_service.dart';

/// Dialog for editing room notes.
///
/// Shows a text editor with save/close buttons.
/// Auto-saves when closed.
class NotesDialog extends ConsumerStatefulWidget {
  const NotesDialog({required this.roomId, super.key});
  final String roomId;

  /// Show the notes dialog.
  static Future<void> show(BuildContext context, String roomId) {
    return showDialog<void>(
      context: context,
      builder: (context) => NotesDialog(roomId: roomId),
    );
  }

  @override
  ConsumerState<NotesDialog> createState() => _NotesDialogState();
}

class _NotesDialogState extends ConsumerState<NotesDialog> {
  late TextEditingController _controller;
  bool _hasChanges = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();

    // Load notes for this room
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadNotes();
    });
  }

  Future<void> _loadNotes() async {
    await ref.read(notesProvider.notifier).initialize(widget.roomId);
    final content = ref.read(notesProvider).content;
    _controller.text = content;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await ref.read(notesProvider.notifier).saveNotes(_controller.text);
    _hasChanges = false;
  }

  Future<void> _close() async {
    // Auto-save on close if there are changes
    if (_hasChanges) {
      await _save();
    }
    if (mounted) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final notesState = ref.watch(notesProvider);

    return Dialog(
      child: Container(
        width: 600,
        height: 500,
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Row(
              children: [
                Icon(
                  Icons.note_alt_outlined,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'Notes: ${widget.roomId}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const Spacer(),
                if (notesState.isSaving)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                if (_hasChanges && !notesState.isSaving)
                  Text(
                    'Unsaved',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.outline,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 16),

            // Error message
            if (notesState.error != null)
              Container(
                padding: const EdgeInsets.all(8),
                margin: const EdgeInsets.only(bottom: 8),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  notesState.error!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                ),
              ),

            // Text editor
            Expanded(
              child: notesState.isLoaded
                  ? TextField(
                      controller: _controller,
                      maxLines: null,
                      expands: true,
                      textAlignVertical: TextAlignVertical.top,
                      decoration: InputDecoration(
                        hintText:
                            // ignore: lines_longer_than_80_chars (auto-documented)
                            'Write your notes here...\n\nSupports markdown formatting.',
                        filled: true,
                        fillColor: Theme.of(
                          context,
                        ).colorScheme.surfaceContainerLowest,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.all(12),
                      ),
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 14,
                      ),
                      onChanged: (value) {
                        if (!_hasChanges) {
                          setState(() => _hasChanges = true);
                        }
                      },
                    )
                  : const Center(child: CircularProgressIndicator()),
            ),
            const SizedBox(height: 16),

            // Actions
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(onPressed: _save, child: const Text('Save')),
                const SizedBox(width: 8),
                FilledButton(onPressed: _close, child: const Text('Close')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
