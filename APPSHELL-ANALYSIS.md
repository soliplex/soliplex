# White-Label Architecture: App Shell (Separate Repository)

## Overview

This document outlines the architecture for enabling white-label Flutter applications where the app shell resides in a **completely separate repository** from the core Soliplex codebase.

## Current State

| Aspect | Status |
|--------|--------|
| Bundle ID | `ai.soliplex.client` (unified across iOS/macOS/Android) |
| Package Structure | `packages/soliplex_client` exists (HTTP/protocol layer) |
| State Management | Riverpod (manual providers) |
| Authentication | OIDC with flutter_appauth, token refresh |
| Platforms | iOS, macOS, Android, Web |

## Target Architecture

```
soliplex/                              # Repo 1: Core Product
├── src/frontend/
│   ├── packages/
│   │   ├── soliplex_core/             # NEW: Extracted shared package
│   │   │   ├── lib/
│   │   │   │   ├── core/              # Auth, providers, networking
│   │   │   │   ├── features/          # Reusable UI features
│   │   │   │   ├── widgets/           # Shared widget library
│   │   │   │   └── soliplex_core.dart # Public barrel export
│   │   │   └── pubspec.yaml
│   │   ├── soliplex_client/           # Existing HTTP/protocol layer
│   │   └── soliplex_client_native/    # Existing native adapters
│   ├── lib/
│   │   └── main.dart                  # Soliplex app shell (thin wrapper)
│   ├── ios/                           # Soliplex platform configs
│   ├── android/
│   └── macos/

whitelabel_customer/                   # Repo 2: Customer App Shell (SEPARATE REPO)
├── lib/
│   └── main.dart                      # Customer entry point, wires config
├── ios/                               # Customer's own bundle ID, icons, signing
├── android/                           # Customer's own applicationId
├── macos/                             # Customer's own bundle ID
├── assets/                            # Customer branding (logos, images)
└── pubspec.yaml                       # Depends on soliplex_core via git
```

## What Goes Where

### `soliplex_core` Package (Shared/Reusable)

- **UI Components**: Buttons, inputs, dialogs, base screens, chat widgets
- **Business Logic**: Data processing, API interaction via `soliplex_client`
- **Data Models**: All shared model classes
- **Riverpod Providers**: Core state management (auth, threads, rooms, etc.)
- **Navigation**: Route definitions and navigator service (not initial route)
- **Theme Support**: Base theme definitions with override hooks
- **Auth Infrastructure**: OIDC flow logic (but not client-specific config)

### App Shell (Customer) - Full Ownership

- **Entry Point**: `main.dart` with customer-specific bootstrap
- **Platform Directories**: Complete ownership of `ios/`, `android/`, `macos/`, `web/`
- **Bundle IDs**: `com.customer.app` or similar (set in native configs)
- **Branding Assets**: App icons, logos, splash screens, fonts
- **OIDC Configuration**: Client ID, redirect URI, issuer URL
- **Theme Overrides**: Colors, typography customizations
- **Feature Flags**: Enable/disable core features as needed

## Configuration Injection Pattern

The core package defines an abstract configuration contract; the app shell provides the implementation:

```dart
// In soliplex_core/lib/core/config/app_config.dart
abstract class AppConfig {
  String get appName;
  String get baseUrl;
  String get oidcClientId;
  String get oidcRedirectUri;
  String get oidcIssuer;
  ThemeData get lightTheme;
  ThemeData get darkTheme;
}

// In soliplex_core - provider expects implementation
final appConfigProvider = Provider<AppConfig>((ref) {
  throw UnimplementedError('AppConfig must be overridden by app shell');
});
```

```dart
// In whitelabel_customer/lib/config/customer_config.dart
class CustomerConfig implements AppConfig {
  @override String get appName => 'Customer App';
  @override String get baseUrl => 'https://api.customer.com';
  @override String get oidcClientId => 'customer-mobile-client';
  // ... etc
}

// In whitelabel_customer/lib/main.dart
void main() {
  runApp(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(CustomerConfig()),
      ],
      child: const SoliplexApp(),
    ),
  );
}
```

## Dependency Management Options

| Method | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Git dependency** | Simple, branch/tag pinning, no publishing overhead | Requires git access, no semantic version resolution | **Recommended** |
| **Private pub server** | Full version control, semantic versioning | Infrastructure overhead, publishing workflow | For enterprise scale |
| **Git submodule** | Direct source access | Complex to manage, sync issues | Avoid |
| **Monorepo** | Single source of truth | Doesn't meet separate-repo requirement | N/A |

### Git Dependency Example (Customer's pubspec.yaml)

```yaml
dependencies:
  soliplex_core:
    git:
      url: git@github.com:your-org/soliplex.git
      path: src/frontend/packages/soliplex_core
      ref: v1.0.0  # Or branch: stable

  soliplex_client:
    git:
      url: git@github.com:your-org/soliplex.git
      path: src/frontend/packages/soliplex_client
      ref: v1.0.0
```

## Bundle ID Ownership

Since the customer owns the entire platform directories, bundle IDs are straightforward:

| Platform | File | Customer Sets |
|----------|------|---------------|
| **iOS** | `ios/Runner/Info.plist`, `*.xcconfig` | `com.customer.app` |
| **Android** | `android/app/build.gradle.kts` | `applicationId = "com.customer.app"` |
| **macOS** | `macos/Runner/Configs/AppInfo.xcconfig` | `PRODUCT_BUNDLE_IDENTIFIER = com.customer.app` |

**URL Schemes**: Each app shell configures its own OIDC callback scheme matching its bundle ID.

## Key Benefits of This Approach

1. **Complete Isolation**: Customer repo has no Soliplex-specific artifacts
2. **Independent Releases**: Customer can release on their own schedule
3. **Clean Bundle ID Ownership**: No flavor complexity, customer owns native layer
4. **Scalable**: Additional white-label apps follow the same pattern
5. **Clear Boundaries**: Core team maintains `soliplex_core`, app teams maintain shells

## Pitfalls to Avoid

- **Over-abstraction**: Don't extract everything upfront; iterate as needs emerge
- **Tight coupling**: Use interfaces and DI; avoid hardcoded assumptions in core
- **Breaking changes**: Use semantic versioning on `soliplex_core`, document migrations
- **Asset conflicts**: Establish clear asset naming conventions

## Migration Steps (High-Level)

1. **Extract `soliplex_core`**: Move shared code into new package with public API
2. **Define config contract**: Abstract `AppConfig` with required extension points
3. **Refactor Soliplex app**: Make it a thin shell consuming `soliplex_core`
4. **Scaffold customer repo**: Fresh Flutter project, add git dependencies
5. **Implement customer config**: Branding, OIDC settings, theme overrides
6. **Configure platforms**: Set bundle IDs, app icons, URL schemes
