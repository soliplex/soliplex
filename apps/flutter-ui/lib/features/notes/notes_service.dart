import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// Conditional imports for file-based persistence (non-web only)
import 'package:soliplex/features/notes/notes_service_io.dart'
    if (dart.library.html) 'notes_service_web.dart'
    as platform;

/// Service for persisting room notes to local markdown files.
///
/// On native platforms, notes are stored per-room in:
/// `{documents}/soliplex_notes/{room_id}.md`
///
/// On web, notes are NOT supported - the UI is hidden via kIsWeb check.
class NotesService {
  NotesService({required this.roomId});
  final String roomId;
  String _content = '';
  bool _loaded = false;

  /// Get the current note content.
  String get content => _content;

  /// Check if notes have been loaded.
  bool get isLoaded => _loaded;

  /// Check if notes feature is supported on this platform.
  static bool get isSupported => platform.isNotesSupported;

  /// Load notes from storage.
  Future<String> loadNotes() async {
    if (_loaded) return _content;

    try {
      final content = await platform.loadNotesData(roomId);
      _content = content ?? '';
      _loaded = true;
    } on Object catch (e) {
      debugPrint('NotesService: Error loading notes: $e');
      _content = '';
      _loaded = true;
    }
    return _content;
  }

  /// Save notes to storage.
  Future<void> saveNotes(String content) async {
    _content = content;
    try {
      await platform.saveNotesData(roomId, content);
    } on Object catch (e) {
      debugPrint('NotesService: Error saving notes: $e');
      rethrow;
    }
  }
}

/// State for the notes provider.
class NotesState {
  const NotesState({
    this.content = '',
    this.isLoaded = false,
    this.isSaving = false,
    this.error,
  });
  final String content;
  final bool isLoaded;
  final bool isSaving;
  final String? error;

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
  NotesNotifier() : super(const NotesState());
  NotesService? _service;

  /// Initialize the service for a room.
  Future<void> initialize(String roomId) async {
    _service = NotesService(roomId: roomId);
    state = const NotesState(); // Reset state

    try {
      final content = await _service!.loadNotes();
      state = NotesState(content: content, isLoaded: true);
    } on Object catch (e) {
      state = NotesState(isLoaded: true, error: 'Failed to load notes: $e');
    }
  }

  /// Save notes.
  Future<void> saveNotes(String content) async {
    if (_service == null) return;

    state = state.copyWith(isSaving: true, clearError: true);

    try {
      await _service!.saveNotes(content);
      state = state.copyWith(content: content, isSaving: false);
    } on Object catch (e) {
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
