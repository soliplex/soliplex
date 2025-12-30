// To parse this JSON data, do
//
//     final filterDocuments = filterDocumentsFromJson(jsonString);

import 'dart:convert';

FilterDocuments filterDocumentsFromJson(String str) =>
    FilterDocuments.fromJson(json.decode(str) as Map<String, dynamic>);

String filterDocumentsToJson(FilterDocuments data) =>
    json.encode(data.toJson());

/// Documents selected by the user to be used to answer a question
///
/// This model describes the 'filter_documents' key in the AG-UI state.
///
/// If 'document_ids' is empty or None, or if the 'filter_documents'
/// key is not present in the AG-UI state, no filter is applied:  the
/// 'ask_with_rich_citations' tool will return all documents matching
/// the query from the LLM.
class FilterDocuments {
  FilterDocuments({
    this.documentIds,
  });

  factory FilterDocuments.fromJson(Map<String, dynamic> json) =>
      FilterDocuments(
        documentIds: json['document_ids'] == null
            ? []
            : List<String>.from(
                (json['document_ids']! as List<dynamic>)
                    .map((x) => x as String),
              ),
      );

  final List<String>? documentIds;

  Map<String, dynamic> toJson() => {
        'document_ids': documentIds == null
            ? []
            : List<dynamic>.from(documentIds!.map((x) => x)),
      };
}
