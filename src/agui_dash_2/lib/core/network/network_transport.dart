import 'package:ag_ui/ag_ui.dart' as ag_ui;

import 'cancel_token.dart';

/// Abstract interface for network transport.
///
/// This abstraction allows pluggable networking backends:
/// - HttpTransport: Web-compatible using ag_ui.AgUiClient
/// - Future: NativeTransport for NSURLSession, etc.
abstract class NetworkTransport {
  /// Run an agent and return a stream of events.
  ///
  /// The [cancelToken] can be used to abort the operation.
  /// Throws [CancelledException] if cancelled.
  Stream<ag_ui.BaseEvent> runAgent({
    required String endpoint,
    required ag_ui.RunAgentInput input,
    CancelToken? cancelToken,
  });

  /// Cancel an active run on the server.
  ///
  /// This notifies the server to stop processing. The client-side
  /// stream should also be cancelled via [CancelToken].
  Future<void> cancelRun({
    required String roomId,
    required String threadId,
    required String runId,
  });

  /// Make a POST request to the server.
  Future<Map<String, dynamic>> post(
    Uri uri,
    Map<String, dynamic> body,
  );

  /// Close the transport and release resources.
  Future<void> close();
}
