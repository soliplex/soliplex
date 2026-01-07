# Backend Bug: [Errno 2] No such file or directory

## Summary

Backend returns Python `[Errno 2] No such file or directory` error when fetching
thread messages after switching rooms.

## Reproduction Steps

1. Log into the app
2. Navigate to room "haiku"
3. Create or view a thread, send a message (works fine)
4. Switch to room "gitea"
5. The app auto-selects a thread (from last-viewed or first in list)
6. Error appears: "An unexpected error occurred. [Errno 2] No such file or directory"

## Technical Details

### Frontend API Call

```text
GET /api/v1/rooms/{roomId}/agui/{threadId}
```

The frontend calls `SoliplexApi.getThreadMessages(roomId, threadId)` which hits
this endpoint to retrieve all runs and events for message reconstruction.

### Error Source

The error `[Errno 2]` is a Python POSIX error (`ENOENT`) indicating a file or
directory doesn't exist. This suggests the backend is trying to read from the
filesystem (likely the thread's event store or run data) and the path doesn't
exist.

### Observed Behavior

- Thread ID: `82d06514-04d8-4131-bec6-f08012275ea6`
- Room: `gitea`
- The thread appears in the sidebar (meaning `GET /rooms/{roomId}/threads` succeeded)
- But loading messages fails

### Hypothesis

Possible causes:

1. **Thread exists in DB but run data missing**: The thread was created but its
   run/event files were never written or were deleted
2. **Cross-room thread reference**: The thread ID might be from a different room
   and the backend is looking in the wrong room's directory
3. **Race condition**: Thread creation succeeded but async file write failed
4. **Storage path misconfiguration**: Backend storage paths may be misconfigured
   for this specific room

## Backend Investigation Needed

1. Check the backend logs for the full stack trace when this error occurs
2. Verify the storage path structure for room "gitea"
3. Confirm the thread `82d06514-04d8-4131-bec6-f08012275ea6` exists and has
   associated run data
4. Check if the error is reproducible with other threads in the gitea room

## Frontend Handling

The frontend correctly displays the error via `ErrorDisplay` widget. The error
flows through:

```text
ThreadMessageCache.getMessages()
  -> SoliplexApi.getThreadMessages()
  -> HttpTransport.request()
  -> Backend returns 500 with error message
  -> ApiException thrown
  -> MessageFetchException wrapper
  -> allMessagesProvider error state
  -> MessageList shows ErrorDisplay with Retry button
```

## Priority

Medium - The app handles the error gracefully but users cannot view thread
history in affected rooms.

## Date Reported

2025-01-07
