import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:soliplex/core/network/cancel_token.dart';
import 'package:soliplex/core/network/network_transport.dart';

/// A fake network transport for testing.
///
/// Allows controlling:
/// - Events to emit
/// - Response delays
/// - Errors to throw
/// - Tracking of calls made
class FakeNetworkTransport implements NetworkTransport {
  FakeNetworkTransport({
    this.eventsToEmit = const [],
    this.responseDelay = Duration.zero,
    this.errorToThrow,
    this.throwBeforeEvents = false,
    this.postResponse = const {},
  });

  /// Events to emit when [runAgent] is called.
  final List<ag_ui.BaseEvent> eventsToEmit;

  /// Delay before emitting each event.
  final Duration responseDelay;

  /// Exception to throw (if any).
  final Exception? errorToThrow;

  /// Whether to throw error before or after emitting events.
  final bool throwBeforeEvents;

  /// Number of times [runAgent] was called.
  int runAgentCallCount = 0;

  /// Captured inputs from [runAgent] calls.
  final List<ag_ui.RunAgentInput> capturedInputs = [];

  /// Captured endpoints from [runAgent] calls.
  final List<String> capturedEndpoints = [];

  /// Number of times [cancelRun] was called.
  int cancelRunCallCount = 0;

  /// Number of times [post] was called.
  int postCallCount = 0;

  /// Response to return from [post].
  Map<String, dynamic> postResponse;

  /// Whether the transport has been closed.
  bool isClosed = false;

  /// Fake runAgent implementation for testing.
  /// Note: This is NOT part of NetworkTransport interface (SSE is via
  /// AgUiClient).
  Stream<ag_ui.BaseEvent> runAgent({
    required String endpoint,
    required ag_ui.RunAgentInput input,
    CancelToken? cancelToken,
  }) async* {
    runAgentCallCount++;
    capturedInputs.add(input);
    capturedEndpoints.add(endpoint);

    cancelToken?.throwIfCancelled();

    if (throwBeforeEvents && errorToThrow != null) {
      throw errorToThrow!;
    }

    for (final event in eventsToEmit) {
      if (cancelToken?.isCancelled ?? false) {
        break;
      }

      if (responseDelay > Duration.zero) {
        await Future.delayed(responseDelay);
      }

      if (cancelToken?.isCancelled ?? false) {
        break;
      }

      yield event;
    }

    if (!throwBeforeEvents && errorToThrow != null) {
      throw errorToThrow!;
    }
  }

  @override
  Future<void> cancelRun({
    required String roomId,
    required String threadId,
    required String runId,
  }) async {
    cancelRunCallCount++;
  }

  @override
  Future<Map<String, dynamic>> post(Uri uri, Map<String, dynamic> body) async {
    postCallCount++;
    return postResponse;
  }

  @override
  Future<void> close() async {
    isClosed = true;
  }

  /// Resets all tracking state.
  void reset() {
    runAgentCallCount = 0;
    capturedInputs.clear();
    capturedEndpoints.clear();
    cancelRunCallCount = 0;
    postCallCount = 0;
    isClosed = false;
  }
}
