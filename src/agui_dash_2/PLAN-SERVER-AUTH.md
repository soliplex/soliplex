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
| `pubspec.yaml` | Add flutter_secure_storage, uni_links |
| `android/app/src/main/AndroidManifest.xml` | Deep link scheme |
| `ios/Runner/Info.plist` | URL scheme |
| `macos/Runner/Info.plist` | URL scheme |

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
  uni_links: ^0.5.1               # Deep link handling (mobile)
  url_launcher: ^6.2.0            # Already have - for OIDC redirect
```

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
| 4. Integration & Polish | 1-2 |
| **Total** | **5-9 days** |
