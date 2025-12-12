# Plan: Server Configuration & OIDC Authentication

## Overview

First-run experience for connecting to a Soliplex server, with support for:
- URL configuration (default: localhost:8000)
- Server discovery (check if server exists, get auth requirements)
- OIDC authentication (when required)
- Token management (storage, refresh, expiry)
- Server history (previously connected servers)
- Mobile-specific OIDC flow (app scheme redirects)

---

## Server API Reference

### Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | GET | Returns available OIDC providers (empty if auth disabled) |
| `/login/{system}` | GET | Initiates OIDC redirect flow |
| `/auth/{system}` | GET | Callback - returns tokens via redirect |
| `/user_info` | GET | Validate token, get user profile |
| `/rooms` | GET | Test connectivity (requires auth if enabled) |

### Auth Response Model

```dart
class OIDCAuthSystem {
  final String id;           // e.g., "keycloak"
  final String title;        // Display name
  final String serverUrl;    // OIDC provider URL
  final String clientId;
  final String? scope;
}
```

### Token Response (via redirect URL params)

```
?token={access_token}
&refresh_token={refresh_token}
&expires_in={seconds}
&refresh_expires_in={seconds}
```

---

## Architecture

### Data Models

```dart
/// A configured server connection
class ServerConnection {
  final String id;           // UUID
  final String url;          // e.g., "https://api.example.com"
  final String? displayName; // User-friendly name
  final bool requiresAuth;
  final String? authProviderId;  // Which OIDC provider used
  final DateTime lastConnected;
  final DateTime? tokenExpiry;
  final String? accessToken;     // Stored securely
  final String? refreshToken;    // Stored securely
}

/// Server discovery result
class ServerInfo {
  final String url;
  final bool isReachable;
  final bool authDisabled;           // No auth required
  final List<OIDCAuthSystem> oidcProviders;
  final String? error;
}
```

### Services

```
lib/core/services/
├── server_config_service.dart     # Server URL management, history
├── auth_service.dart              # OIDC flow, token management
├── secure_storage_service.dart    # Platform-secure token storage
```

### State Management

```dart
// Selected server configuration
final serverConfigProvider = StateNotifierProvider<ServerConfigNotifier, ServerConfig?>(...);

// Authentication state
final authStateProvider = StateNotifierProvider<AuthNotifier, AuthState>(...);

// Server history
final serverHistoryProvider = FutureProvider<List<ServerConnection>>(...);
```

---

## User Flows

### Flow 1: First Launch (No Server Configured)

```
┌─────────────────────────────────────────┐
│         Welcome to Soliplex             │
│                                         │
│  Connect to a server to get started     │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ http://localhost:8000          │   │
│  └─────────────────────────────────┘   │
│                                         │
│        [ Connect ]                      │
│                                         │
│  ────────── Or ──────────              │
│                                         │
│  Recent servers: (none)                 │
└─────────────────────────────────────────┘
```

### Flow 2: Server Discovery

After user enters URL:

1. **Probe server**: GET `{url}/login`
   - Success → Parse OIDC providers
   - 404/Error → Server unreachable or not Soliplex

2. **If no OIDC providers** (auth disabled):
   - Skip auth, connect directly
   - Save to history

3. **If OIDC providers exist**:
   - Show provider selection (if multiple)
   - Initiate OIDC flow

### Flow 3: OIDC Authentication (Web)

```
1. User clicks "Login with {Provider}"
2. App opens: {serverUrl}/login/{providerId}?return_to={appUrl}
3. Browser redirects to OIDC provider
4. User authenticates
5. OIDC redirects to: {serverUrl}/auth/{providerId}
6. Server redirects to: {appUrl}?token=...&refresh_token=...
7. App captures tokens from URL
8. Save connection + tokens
```

### Flow 4: OIDC Authentication (Mobile)

Mobile requires a custom URL scheme for the return redirect.

```
1. Register app scheme: soliplex://
2. User clicks "Login with {Provider}"
3. App opens browser/WebView: {serverUrl}/login/{providerId}?return_to=soliplex://auth
4. OIDC flow completes
5. Server redirects to: soliplex://auth?token=...&refresh_token=...
6. OS returns to app via deep link
7. App captures tokens from deep link
8. Save connection + tokens
```

**Platform-specific setup:**
- **iOS**: Info.plist CFBundleURLSchemes
- **Android**: intent-filter in AndroidManifest.xml
- **macOS**: Info.plist CFBundleURLSchemes
- **Web**: Use window.location for return_to

### Flow 5: Token Refresh

```dart
// On app startup or before API call
if (tokenExpiry < DateTime.now().add(Duration(minutes: 5))) {
  await refreshToken();
}
```

### Flow 6: Switch Servers

```
┌─────────────────────────────────────────┐
│  ☰  Server: api.example.com      [ ⚙ ]│
├─────────────────────────────────────────┤
│                                         │
│  Recent Servers:                        │
│  ┌─────────────────────────────────┐   │
│  │ ✓ api.example.com (connected)   │   │
│  │   localhost:8000                │   │
│  │   staging.example.com           │   │
│  └─────────────────────────────────┘   │
│                                         │
│  [ + Add New Server ]                   │
│                                         │
└─────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Day 1-2)

1. **SecureStorageService** - Token/credential storage
   - Flutter Secure Storage (mobile)
   - Web: localStorage with encryption consideration

2. **ServerConfigService** - URL management
   - Probe server (GET /login)
   - Parse OIDC providers
   - Validate connectivity

3. **Data models** - ServerConnection, ServerInfo, AuthState

### Phase 2: Server Selection UI (Day 2-3)

1. **ServerSetupScreen** - First-run experience
   - URL input with validation
   - "Connect" button with loading state
   - Error display for unreachable servers

2. **ServerHistoryWidget** - Previous connections
   - List of saved servers
   - Quick-switch capability
   - Delete/edit connections

3. **ServerSelector** - Header widget for switching
   - Current server indicator
   - Dropdown to switch

### Phase 3: OIDC Authentication (Day 3-5)

1. **AuthService** - Token management
   - initiate OIDC flow
   - Handle callback (web)
   - Token storage/refresh
   - Logout

2. **OIDCProviderSelector** - When multiple providers
   - List available providers
   - Provider icons/branding

3. **Deep Link Handler (Mobile)** - Platform-specific
   - iOS: Handle soliplex:// scheme
   - Android: Handle soliplex:// scheme
   - Parse tokens from URL

### Phase 4: Integration (Day 5-6)

1. **App startup flow**
   - Check for saved server
   - Validate token if exists
   - Show setup if no server
   - Show login if token expired

2. **AgUiService integration**
   - Pass auth headers
   - Handle 401 responses
   - Auto-refresh tokens

3. **UI polish**
   - Loading states
   - Error handling
   - Animations

---

## Technical Details

### Secure Storage

```dart
// Mobile: flutter_secure_storage
// Web: Consider encrypted localStorage or session-only

abstract class SecureStorageService {
  Future<void> write(String key, String value);
  Future<String?> read(String key);
  Future<void> delete(String key);
  Future<void> deleteAll();
}
```

### Deep Link Configuration

**Android (AndroidManifest.xml):**
```xml
<intent-filter>
  <action android:name="android.intent.action.VIEW"/>
  <category android:name="android.intent.category.DEFAULT"/>
  <category android:name="android.intent.category.BROWSABLE"/>
  <data android:scheme="soliplex" android:host="auth"/>
</intent-filter>
```

**iOS (Info.plist):**
```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>soliplex</string>
    </array>
  </dict>
</array>
```

### Auth Headers

```dart
// Add to all API requests when authenticated
Map<String, String> get authHeaders {
  if (_accessToken != null) {
    return {'Authorization': 'Bearer $_accessToken'};
  }
  return {};
}
```

### Token Refresh Flow

```dart
Future<bool> refreshToken() async {
  // Note: Server uses standard OIDC refresh
  // May need to call OIDC provider directly for refresh
  // Or implement refresh endpoint on server

  // For now: re-authenticate if token expired
  return false;
}
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `lib/core/services/secure_storage_service.dart` | Secure credential storage |
| `lib/core/services/server_config_service.dart` | Server discovery & management |
| `lib/core/services/auth_service.dart` | OIDC flow & token management |
| `lib/core/models/server_models.dart` | ServerConnection, ServerInfo |
| `lib/features/server/server_setup_screen.dart` | First-run setup |
| `lib/features/server/server_history_widget.dart` | Saved servers list |
| `lib/features/server/oidc_login_screen.dart` | OIDC provider selection |
| `lib/features/server/server_selector.dart` | Header server switcher |

## Files to Modify

| File | Changes |
|------|---------|
| `lib/main.dart` | App startup flow, deep link handling |
| `lib/core/services/agui_service.dart` | Auth header injection |
| `pubspec.yaml` | Add flutter_secure_storage, app_links, go_router |
| `android/app/src/main/AndroidManifest.xml` | Deep link scheme |
| `ios/Runner/Info.plist` | URL scheme |
| `macos/Runner/Info.plist` | URL scheme |
| `windows/runner/main.cpp` | Deep link argument handling |
| `linux/my_application.cc` | Deep link argument handling |
| `linux/soliplex.desktop` | URL scheme handler (create) |

---

## Open Questions

1. **Token refresh**: Does server support refresh endpoint, or re-auth required?
2. **Multiple servers simultaneously**: Allow connecting to multiple servers at once?
3. **Offline mode**: Cache rooms/conversations for offline viewing?
4. **Server auto-discovery**: mDNS/Bonjour for local servers?
5. **Biometric protection**: Require FaceID/fingerprint to access saved credentials?

---

## Dependencies to Add

```yaml
dependencies:
  flutter_secure_storage: ^9.0.0  # Secure credential storage
  app_links: ^6.3.3               # Cross-platform deep links (iOS, Android, macOS, Windows, Linux)
  url_launcher: ^6.2.0            # Already have - for OIDC redirect
  go_router: ^14.6.0              # Web routing with deep link support
```

**Note**: `app_links` supersedes `uni_links` and provides unified handling across all desktop platforms:
- Automatic Windows registry setup during build
- macOS Info.plist integration
- Linux .desktop file generation helper
- Mobile (iOS/Android) intent handling

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Token storage security | Medium | Use platform secure storage, not SharedPreferences |
| Deep link hijacking | Low | Validate redirect source, use state parameter |
| Token expiry race | Medium | Proactive refresh before expiry |
| Multi-platform testing | High | Test on iOS, Android, Web, macOS |
| OIDC provider variations | Medium | Test with multiple providers |

---

## Timeline Estimate

| Phase | Days |
|-------|------|
| 1. Core Infrastructure | 1-2 |
| 2. Server Selection UI | 1-2 |
| 3. OIDC Authentication | 2-3 |
| 4. Deep Link System | 1-2 |
| 5. Integration & Polish | 1-2 |
| **Total** | **6-11 days** |

---

## Extensible Deep Link System

### Overview

Universal deep link handling that works across all platforms:
- **Mobile (iOS/Android)**: Custom scheme `soliplex://`
- **macOS**: Custom scheme `soliplex://`
- **Windows**: Custom scheme `soliplex://` (registry-based)
- **Linux**: Custom scheme `soliplex://` (xdg-open / .desktop file)
- **Web**: URL path/fragment-based routing

### URL Formats

| Platform | Format | Example |
|----------|--------|---------|
| Mobile | `soliplex://{action}?{params}` | `soliplex://chat?room=genui&text=Hello` |
| Web | `https://app.example.com/#/{action}?{params}` | `.../#/chat?room=genui&text=Hello` |
| Web (path) | `https://app.example.com/{action}?{params}` | `.../chat?room=genui&text=Hello` |

### Architecture

```dart
/// Base class for all deep link actions
abstract class DeepLinkAction {
  /// Unique action identifier (e.g., "auth", "chat", "room")
  String get actionId;

  /// Parse parameters from URI
  factory DeepLinkAction.fromUri(Uri uri);

  /// Execute the action (navigate, submit, etc.)
  Future<void> execute(BuildContext context, WidgetRef ref);
}

/// Registry of all supported deep link actions
class DeepLinkRegistry {
  final Map<String, DeepLinkAction Function(Uri)> _handlers = {};

  void register(String actionId, DeepLinkAction Function(Uri) factory);
  DeepLinkAction? parse(Uri uri);
}

/// Service that handles incoming deep links
class DeepLinkService {
  final DeepLinkRegistry registry;

  // Platform-specific listeners
  StreamSubscription? _mobileSubscription;  // uni_links

  void initialize();
  void handleUri(Uri uri);
  void dispose();
}
```

### Supported Actions

#### 1. Auth Callback (`/auth`)

OIDC callback with tokens.

```
soliplex://auth?token={jwt}&refresh_token={jwt}&expires_in=3600

Web: /#/auth?token=...
```

```dart
class AuthCallbackAction extends DeepLinkAction {
  final String accessToken;
  final String refreshToken;
  final int expiresIn;

  @override
  String get actionId => 'auth';

  @override
  Future<void> execute(BuildContext context, WidgetRef ref) async {
    final authService = ref.read(authServiceProvider);
    await authService.handleTokenCallback(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresIn: expiresIn,
    );
    // Navigate to home or previous screen
    context.go('/');
  }
}
```

#### 2. Chat in Room (`/chat`)

Open a room, optionally with pre-filled text and auto-submit.

```
soliplex://chat?room=genui&text=Hello%20world&submit=true

Web: /#/chat?room=genui&text=Hello%20world&submit=true
```

```dart
class ChatAction extends DeepLinkAction {
  final String roomId;
  final String? text;
  final bool autoSubmit;

  @override
  String get actionId => 'chat';

  @override
  Future<void> execute(BuildContext context, WidgetRef ref) async {
    // Select the room
    ref.read(selectedRoomProvider.notifier).state = roomId;

    // Pre-fill text if provided
    if (text != null) {
      // Get input controller and set text
      final inputController = ref.read(chatInputControllerProvider);
      inputController.text = text!;

      // Auto-submit if requested
      if (autoSubmit) {
        // Small delay to let UI settle
        await Future.delayed(const Duration(milliseconds: 100));
        ref.read(chatProvider.notifier).sendMessage(text!);
      }
    }

    // Navigate to chat screen
    context.go('/room/$roomId');
  }
}
```

#### 3. Open Room (`/room`)

Navigate to a specific room.

```
soliplex://room/genui
soliplex://room?id=genui

Web: /#/room/genui
```

```dart
class OpenRoomAction extends DeepLinkAction {
  final String roomId;

  @override
  String get actionId => 'room';

  @override
  Future<void> execute(BuildContext context, WidgetRef ref) async {
    ref.read(selectedRoomProvider.notifier).state = roomId;
    context.go('/room/$roomId');
  }
}
```

#### 4. Connect to Server (`/connect`)

Connect to a specific server (useful for QR codes, sharing).

```
soliplex://connect?url=https://api.example.com

Web: /#/connect?url=https://api.example.com
```

```dart
class ConnectServerAction extends DeepLinkAction {
  final String serverUrl;

  @override
  String get actionId => 'connect';

  @override
  Future<void> execute(BuildContext context, WidgetRef ref) async {
    final serverConfig = ref.read(serverConfigProvider.notifier);
    await serverConfig.connectToServer(serverUrl);
    // Will trigger auth flow if needed
  }
}
```

#### 5. Share/Import Thread (`/thread`)

Open or import a shared conversation thread.

```
soliplex://thread?id=abc123&room=genui

Web: /#/thread?id=abc123&room=genui
```

#### 6. Execute Command (`/command`)

Run a slash command in a room.

```
soliplex://command?room=genui&cmd=/search%20staff

Web: /#/command?room=genui&cmd=/search%20staff
```

### Web-Specific Handling

For web, we use GoRouter's redirect and initial location handling:

```dart
final router = GoRouter(
  initialLocation: _getInitialLocation(),
  redirect: (context, state) {
    // Check for deep link parameters in URL
    final uri = Uri.parse(state.uri.toString());
    if (_isDeepLinkAction(uri)) {
      // Queue action for execution after app initialized
      _pendingDeepLink = uri;
      return '/'; // Redirect to home, action executes after
    }
    return null;
  },
  routes: [...],
);

String _getInitialLocation() {
  // On web, check window.location for deep link
  if (kIsWeb) {
    final uri = Uri.parse(html.window.location.href);
    if (_isDeepLinkAction(uri)) {
      return uri.path;
    }
  }
  return '/';
}
```

### Registration

```dart
void registerDeepLinkActions(DeepLinkRegistry registry) {
  registry.register('auth', (uri) => AuthCallbackAction.fromUri(uri));
  registry.register('chat', (uri) => ChatAction.fromUri(uri));
  registry.register('room', (uri) => OpenRoomAction.fromUri(uri));
  registry.register('connect', (uri) => ConnectServerAction.fromUri(uri));
  registry.register('thread', (uri) => ThreadAction.fromUri(uri));
  registry.register('command', (uri) => CommandAction.fromUri(uri));
}
```

### Platform Setup

**Web (index.html or router config):**
```dart
// Handle fragment-based routing
// /#/chat?room=genui&text=Hello
// Already handled by GoRouter with hashUrlStrategy
```

**Windows (windows/runner/main.cpp or installer):**

Register URL scheme in Windows Registry (during install):
```reg
[HKEY_CLASSES_ROOT\soliplex]
@="URL:Soliplex Protocol"
"URL Protocol"=""

[HKEY_CLASSES_ROOT\soliplex\shell]

[HKEY_CLASSES_ROOT\soliplex\shell\open]

[HKEY_CLASSES_ROOT\soliplex\shell\open\command]
@="\"C:\\Program Files\\Soliplex\\soliplex.exe\" \"%1\""
```

Or via Flutter's protocol handler registration:
```dart
// Use app_links package which handles Windows protocol registration
// during build/install process
```

**Linux (.desktop file):**

Create `soliplex.desktop` in `~/.local/share/applications/`:
```ini
[Desktop Entry]
Name=Soliplex
Exec=/opt/soliplex/soliplex %u
Type=Application
Terminal=false
MimeType=x-scheme-handler/soliplex;
```

Register the handler:
```bash
xdg-mime default soliplex.desktop x-scheme-handler/soliplex
update-desktop-database ~/.local/share/applications/
```

**All Platforms (app_links):**
```dart
// Single unified handler for all platforms
void _initDeepLinks() async {
  final appLinks = AppLinks();

  // Handle app opened via deep link (cold start)
  final initialLink = await appLinks.getInitialLink();
  if (initialLink != null) {
    _handleDeepLink(initialLink);
  }

  // Handle deep links while app is running (warm start)
  _subscription = appLinks.uriLinkStream.listen((Uri uri) {
    _handleDeepLink(uri);
  });
}

void _handleDeepLink(Uri uri) {
  final action = _registry.parse(uri);
  if (action != null) {
    action.execute(context, ref);
  }
}
```

**Desktop-specific notes:**
- **Windows**: Deep links arrive as command-line arguments on app launch, or via window message when app is already running
- **Linux**: Deep links arrive via command-line arguments (`%u` in .desktop file)
- **macOS**: Uses Apple Events (handled by app_links automatically)

### Example: QR Code for Quick Chat

Generate a QR code that:
1. Opens app (or app store if not installed)
2. Connects to server
3. Opens room with pre-filled message

```
soliplex://chat?server=https://api.example.com&room=support&text=I%20need%20help
```

Web fallback URL:
```
https://app.soliplex.io/#/chat?server=https://api.example.com&room=support&text=I%20need%20help
```

### Files to Create

| File | Purpose |
|------|---------|
| `lib/core/services/deep_link_service.dart` | Central deep link handling |
| `lib/core/services/deep_link_registry.dart` | Action registration |
| `lib/core/models/deep_link_actions.dart` | Action implementations |
| `lib/core/models/deep_link_action.dart` | Base action class |

### Future Actions (Extensible)

The registry pattern allows easy addition of new actions:

- `/quiz?id=123` - Open a specific quiz
- `/canvas?import=...` - Import canvas state
- `/settings?tab=appearance` - Open specific settings
- `/search?q=flutter` - Search across rooms
- `/share?content=...` - Share content to a room
