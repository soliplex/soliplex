// reason: dynamic fromJson (parsing API responses)

/// Data model for a RAG document.
///
/// Maps to RAGDocument in backend.
class Document {
  const Document({
    required this.id,
    required this.title,
    required this.createdAt,
    required this.updatedAt,
    this.uri,
    this.metadata = const {},
  });

  factory Document.fromJson(Map<String, dynamic> json) {
    return Document(
      id: json['id'] as String,
      title:
          (json['title'] as String?) ?? (json['uri'] as String?) ?? 'Untitled',
      uri: json['uri'] as String?,
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? {},
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  final String id;
  final String title;
  final String? uri;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;
  final DateTime updatedAt;

  /// Get file size from metadata if available.
  int? get size => metadata['size'] as int?;

  /// Get content type from metadata if available.
  String? get contentType => metadata['content_type'] as String?;

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'uri': uri,
      'metadata': metadata,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }
}
