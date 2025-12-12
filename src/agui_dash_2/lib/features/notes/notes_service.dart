import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

/// Service for persisting room notes to local markdown files.
///
/// Notes are stored per-room in:
/// `{documents}/soliplex_notes/{room_id}.md`
class NotesService {
  final String roomId;
  String _content = '';
  bool _loaded = false;

  NotesService({required this.roomId});

  /// Get the current note content.
  String get content => _content;

  /// Check if notes have been loaded.
  bool get isLoaded => _loaded;

  /// Load notes from disk.
  Future<String> loadNotes() async {
    if (_loaded) return _content;

    try {
      final file = await _getNotesFile();
      if (await file.exists()) {
        _content = await file.readAsString();
      } else {
        _content = '';
      }
      _loaded = true;
    } catch (e) {
      debugPrint('NotesService: Error loading notes: $e');
      _content = '';
      _loaded = true;
    }
    return _content;
  }

  /// Save notes to disk.
  Future<void> saveNotes(String content) async {
    _content = content;
    try {
      final file = await _getNotesFile();
      await file.writeAsString(content);
    } catch (e) {
      debugPrint('NotesService: Error saving notes: $e');
      rethrow;
    }
  }

  /// Get the notes file for this room.
  Future<File> _getNotesFile() async {
    final directory = await getApplicationDocumentsDirectory();
    final notesDir = Directory('${directory.path}/soliplex_notes');

    if (!await notesDir.exists()) {
      await notesDir.create(recursive: true);
    }

    return File('${notesDir.path}/$roomId.md');
  }
}

/// State for the notes provider.
class NotesState {
  final String content;
  final bool isLoaded;
  final bool isSaving;
  final String? error;

  const NotesState({
    this.content = '',
    this.isLoaded = false,
    this.isSaving = false,
    this.error,
  });

  NotesState copyWith({
    String? content,
    bool? isLoaded,
    bool? isSaving,
    String? error,
    bool clearError = false,
  }) {
    return NotesState(
      content: content ?? this.content,
      isLoaded: isLoaded ?? this.isLoaded,
      isSaving: isSaving ?? this.isSaving,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

/// Notifier for managing notes state.
class NotesNotifier extends StateNotifier<NotesState> {
  NotesService? _service;

  NotesNotifier() : super(const NotesState());

  /// Initialize the service for a room.
  Future<void> initialize(String roomId) async {
    _service = NotesService(roomId: roomId);
    state = const NotesState(); // Reset state

    try {
      final content = await _service!.loadNotes();
      state = NotesState(
        content: content,
        isLoaded: true,
      );
    } catch (e) {
      state = NotesState(
        isLoaded: true,
        error: 'Failed to load notes: $e',
      );
    }
  }

  /// Save notes.
  Future<void> saveNotes(String content) async {
    if (_service == null) return;

    state = state.copyWith(isSaving: true, clearError: true);

    try {
      await _service!.saveNotes(content);
      state = state.copyWith(
        content: content,
        isSaving: false,
      );
    } catch (e) {
      state = state.copyWith(
        isSaving: false,
        error: 'Failed to save notes: $e',
      );
    }
  }

  /// Update content locally (without saving).
  void updateContent(String content) {
    state = state.copyWith(content: content);
  }
}

/// Provider for notes service.
final notesProvider = StateNotifierProvider<NotesNotifier, NotesState>((ref) {
  return NotesNotifier();
});
