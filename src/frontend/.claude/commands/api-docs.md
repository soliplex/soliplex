View the backend API documentation.

When the backend is running, access:
- OpenAPI docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Key API endpoints:
- `GET /api/rooms` - List available rooms
- `GET /api/rooms/{room}/threads` - List threads in a room
- `POST /api/rooms/{room}/threads` - Create new thread
- `POST /api/rooms/{room}/threads/{thread}/query` - Send query to AI
- `GET /api/rooms/{room}/threads/{thread}/events` - SSE event stream

AG-UI endpoints:
- `POST /api/agui/{room}/runs` - Start AG-UI run
- `GET /api/agui/{room}/runs/{run_id}/events` - Stream AG-UI events
