import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/models/document_model.dart';
import 'package:soliplex/core/services/rooms_service.dart';

/// Provides a list of documents for a given room.
///
/// This is a [FutureProvider.family] that takes a `roomId` as a parameter.
/// It fetches documents from the `RoomsService` and exposes them to the UI.
final FutureProviderFamily<List<Document>, String> roomDocumentsProvider =
    FutureProvider.family<List<Document>, String>((
      Ref ref,
      String roomId,
    ) async {
      final roomsService = ref.watch(roomsProvider.notifier);
      // Defer execution to avoid "modifying other providers" error.
      await Future<void>.microtask(() {});
      return roomsService.fetchDocuments(roomId);
    });
