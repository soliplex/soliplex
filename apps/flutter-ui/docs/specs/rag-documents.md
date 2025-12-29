# RAG Documents Listing Specification

**Status:** Draft
**Owner:** @runyaga
**Created:** 2025-12-15

## Context

Rooms configured with RAG (Retrieval-Augmented Generation) capabilities have associated documents that the agent can retrieve information from. Users need visibility into what documents are available in the room's knowledge base.

## Goals

1.  **API Integration**: Consume the `/api/v1/rooms/{room_id}/documents` endpoint.
2.  **Data Modeling**: Define a `Document` model to represent file metadata.
3.  **UI Visualization**: Provide a way for users to view the list of documents within a room.

## Data Model: Document

The `Document` model will capture essential metadata about a file in the RAG system.

```dart
class Document {
  final String id;
  final String filename;
  final String? contentType;
  final DateTime? createdAt;
  final int? size; // size in bytes
  
  // Factory for JSON serialization
  factory Document.fromJson(Map<String, dynamic> json) ...
}
```

## API Specification

### Endpoint

`GET /api/v1/rooms/{room_id}/documents`

### Response Schema

Expected JSON response:

```json
{
  "documents": [
    {
      "id": "doc-123",
      "filename": "annual_report.pdf",
      "contentType": "application/pdf",
      "created_at": "2025-01-01T12:00:00Z",
      "size": 1048576
    },
    ...
  ]
}
```

## Implementation Plan

### 1. Core Layer
-   Create `lib/core/models/document_model.dart`.
-   Update `lib/core/utils/api_constants.dart` with `documents` path segment.
-   Update `lib/core/utils/url_builder.dart` with `roomDocuments(String roomId)` method.
-   Update `lib/core/services/rooms_service.dart`:
    -   Add `fetchDocuments(String roomId)` method to `RoomsNotifier` (or a dedicated service if preferred, but `RoomsNotifier` handles room data).
    -   Alternatively, create a dedicated `DocumentsService` or `RagService` if the logic grows. For listing, `RoomsNotifier` or a simple FutureProvider in the UI layer using `rooms_service` is sufficient.

### 2. Provider Layer
-   Create `roomDocumentsProvider(String roomId)` (Family FutureProvider) in `lib/features/room/providers/document_providers.dart`.
    -   Calls the API via `RoomsService` or direct `HttpTransport`.

### 3. UI Layer
-   **Entry Point**: Add a "Documents" button/icon in the `RoomInfoDrawer` or `RoomAppBar` actions.
-   **Listing Widget**: Create `DocumentListDialog` or `DocumentListScreen`.
    -   Displays list of documents using `ListView`.
    -   Shows filename, size, and date.
    -   Handles loading and error states.

## Future Considerations

-   **Upload**: Ability to upload new documents (POST /documents).
-   **Delete**: Ability to remove documents (DELETE /documents/{id}).
-   **Preview**: Viewing document content.
