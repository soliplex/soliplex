/// Abstract interface for network transport.
///
/// This abstraction allows pluggable networking backends:
/// - HttpTransport: Web-compatible using http.Client
/// - Future: NativeTransport for NSURLSession, etc.
///
/// Note: SSE streaming (runAgent) is handled separately via AgUiClient
/// in ServerConnectionState. This interface is for HTTP POST/cancel only.
abstract class NetworkTransport {
  /// Cancel an active run on the server.
  ///
  /// This notifies the server to stop processing. The client-side
  /// stream should also be cancelled via CancelToken.
  Future<void> cancelRun({
    required String roomId,
    required String threadId,
    required String runId,
  });

  /// Make a POST request to the server.
  Future<Map<String, dynamic>> post(Uri uri, Map<String, dynamic> body);

  /// Close the transport and release resources.
  Future<void> close();
}
