---
name: soliplex-files
description: Upload files and manage documents on a Soliplex server — room-level and thread-level uploads, RAG document listing
---

# Soliplex File Management

This skill covers uploading files to a Soliplex server and viewing available documents in a room's RAG knowledge base.

## Upload a File to a Room

Upload a document to a room's shared knowledge base (available to all conversations in the room):

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/uploads/{room_id} \
  -F "upload_file=@/path/to/document.pdf"
```

Returns HTTP 204 on success.

The `upload_file` field is a standard multipart form file upload. The content type is inferred from the file extension.

## Upload a File to a Thread

Upload a document scoped to a specific conversation thread:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/uploads/{room_id}/{thread_id} \
  -F "upload_file=@/path/to/document.pdf"
```

Returns HTTP 204 on success.

## List Room Documents

View all documents in a room's RAG knowledge base:

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/documents
```

Response:

```json
{
  "room_id": "chat",
  "document_set": {
    "doc_abc123": {
      "id": "doc_abc123",
      "uri": "file:///path/to/original.pdf",
      "title": "Original Document Title",
      "metadata": {},
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  }
}
```

## View a Chunk Visualization

For RAG rooms, view the page images for a specific chunk with the chunk text highlighted:

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/chunk/{chunk_id}
```

Response: `{chunk_id, document_uri, images_base_64: ["..."]}` — base64-encoded page images with the chunk highlighted.
