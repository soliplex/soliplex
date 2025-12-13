# ADR-0001: SSE Delegate Pattern for Thread

| Field | Value |
|-------|-------|
| Status | accepted |
| Date | 2025-12-13 |
| Deciders | runyaga |
| Refs | SPEC:network-transport-layer |

## Context

When wiring SSE through NetworkTransportLayer for inspector visibility, we needed to decide how Thread should access the SSE streaming capability. Thread previously used `ag_ui.AgUiClient` directly, but we wanted SSE traffic to flow through NetworkTransportLayer for observability.

## Options Considered

### Option A: Pass NetworkTransportLayer to Thread

Pass the entire NetworkTransportLayer object to Thread's constructor.

```dart
Thread({
  required NetworkTransportLayer transportLayer,
})
```

- (+) Direct access to all transport layer capabilities
- (-) Tight coupling between Thread and NetworkTransportLayer
- (-) Thread becomes aware of HTTP concerns it doesn't need
- (-) Harder to test - need to mock entire transport layer

### Option B: Delegate Pattern with RunAgentDelegate

Define a typedef for the SSE function signature and inject it.

```dart
typedef RunAgentDelegate = Stream<BaseEvent> Function(
  String endpoint,
  SimpleRunAgentInput input,
);

Thread.withDelegate({
  required RunAgentDelegate runAgent,
})
```

- (+) Loose coupling - Thread only knows about the function signature
- (+) Easy to test - just pass a mock function
- (+) Flexible - can swap implementations without changing Thread
- (+) Thread remains focused on its core responsibility

## Decision

We chose **Option B: Delegate Pattern** because it provides the cleanest separation of concerns. Thread's responsibility is managing conversation threads and SSE event processing, not network transport details. By accepting a simple function delegate, Thread can remain agnostic about where SSE streams come from.

## Consequences

- (+) Thread can be tested with simple mock functions instead of complex mock objects
- (+) NetworkTransportLayer changes don't require Thread changes
- (+) Legacy code path (`Thread(client:)`) continues to work for backward compatibility
- (-) Slight indirection - need to trace through delegate to find actual implementation
- (!) Must ensure delegate is properly wired when creating Thread instances
