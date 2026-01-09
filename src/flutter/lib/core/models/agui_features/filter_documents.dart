// Generated code from quicktype - ignoring style issues
// ignore_for_file: sort_constructors_first
// ignore_for_file: prefer_single_quotes
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: argument_type_not_assignable
// ignore_for_file: unnecessary_ignore

// To parse this JSON data, do
//
//     final filterDocuments = filterDocumentsFromJson(jsonString);

import 'dart:convert';

FilterDocuments filterDocumentsFromJson(String str) =>
    FilterDocuments.fromJson(json.decode(str));

String filterDocumentsToJson(FilterDocuments data) =>
    json.encode(data.toJson());

///Documents selected by the user to be used to answer a question
///
///This model describes the 'filter_documents' key in the AG-UI state.
///
///If 'document_ids' is empty or None, or if the 'filter_documents'
///key is not present in the AG-UI state, no filter is applied:  the
///'ask_with_rich_citations' tool will return all documents matching
///the query from the LLM.
class FilterDocuments {
  final List<String>? documentIds;

  FilterDocuments({
    this.documentIds,
  });

  factory FilterDocuments.fromJson(Map<String, dynamic> json) =>
      FilterDocuments(
        documentIds: json["document_ids"] == null
            ? []
            : List<String>.from(json["document_ids"]!.map((x) => x)),
      );

  Map<String, dynamic> toJson() => {
    "document_ids": documentIds == null
        ? []
        : List<dynamic>.from(documentIds!.map((x) => x)),
  };
}
