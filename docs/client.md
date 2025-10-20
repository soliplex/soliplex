# Client Setup

The Soliplex client is a Flutter web application that provides the user
interface for interacting with the RAG system.

## Prerequisites

- Dart SDK
- Flutter SDK
- Google Chrome (for web development)

## Installation

1. Clone the client repository:
   ```bash
   git clone git@github.com:soliplex/soliplex.git
   cd soliplex/src/gen_ai_client
   ```

2. Install Flutter dependencies:
   ```bash
   flutter pub get
   ```

## Running the Client

Start the Flutter web application:

```bash
flutter run -d chrome
```

This will launch the application in Chrome and provide a development
server with hot reload capabilities.

## Development

The client uses:
- Flutter 3.35+ with Material Design
- Riverpod for state management
- `go_router` for navigation
- WebSocket connections for real-time chat
