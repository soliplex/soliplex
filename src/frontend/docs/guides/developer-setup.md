# Developer Setup Guide

Platform-specific setup instructions for building and running the Soliplex
Flutter frontend.

## Prerequisites

- Flutter SDK (stable channel)
- Xcode (for iOS/macOS)
- CocoaPods (`gem install cocoapods`)

## Quick Start

```bash
# Install dependencies
flutter pub get

# Install iOS/macOS pods
cd ios && pod install && cd ..
cd macos && pod install && cd ..

# Run the app
flutter run -d macos   # or: -d ios, -d chrome
```

## Platform Setup

### macOS

#### Code Signing (Required for Keychain)

macOS apps require code signing to access Keychain for secure token storage.
Each developer must configure their own Apple Developer Team ID:

```bash
# 1. Copy the template
cp macos/Runner/Configs/Local.xcconfig.template macos/Runner/Configs/Local.xcconfig

# 2. Edit Local.xcconfig and add your Team ID
```

Your `Local.xcconfig` should contain:

```text
DEVELOPMENT_TEAM = YOUR_TEAM_ID_HERE
CODE_SIGN_IDENTITY = Apple Development
```

**Finding your Team ID:**

1. Go to <https://developer.apple.com/account>
2. Click "Membership details"
3. Copy the 10-character Team ID (e.g., `XXXXXXXXXX`)

**Verification:**

```bash
flutter build macos --debug
```

If configured correctly, Keychain operations succeed and auth tokens persist
across app restarts.

**Without code signing:** The app runs but Keychain fails silently. Auth works
per-session but tokens don't persist, requiring re-login on each launch.

### iOS

#### Code Signing (Required for Physical Devices)

iOS uses the same xcconfig pattern as macOS:

```bash
# 1. Copy the template
cp ios/Runner/Configs/Local.xcconfig.template ios/Runner/Configs/Local.xcconfig

# 2. Edit Local.xcconfig and add your Team ID
```

Your `Local.xcconfig` should contain:

```text
DEVELOPMENT_TEAM = YOUR_TEAM_ID_HERE
```

#### Simulator vs Device

- **Simulator:** No signing required for debug builds
- **Physical device:** Requires `Local.xcconfig` with valid `DEVELOPMENT_TEAM`

### Web

No special setup required. Run with:

```bash
flutter run -d chrome
```

## Troubleshooting

### Entitlements require signing

```text
"Runner" has entitlements that require signing with a development certificate
```

**Cause:** Missing `Local.xcconfig` or `CODE_SIGN_IDENTITY` not set.

**Fix:** Create `Local.xcconfig` with both `DEVELOPMENT_TEAM` and
`CODE_SIGN_IDENTITY` as shown above.

### Keychain errors on macOS

```text
OSStatus error -25293
```

**Cause:** Missing or invalid code signing configuration.

**Fix:** Follow the macOS code signing setup above.

### Pod install fails

```bash
# Clean and reinstall
cd ios && pod deintegrate && pod install && cd ..
cd macos && pod deintegrate && pod install && cd ..
```

### Flutter version issues

```bash
# Check version
flutter --version

# Upgrade if needed
flutter upgrade
```

## Related Files

| File | Purpose |
|------|---------|
| `macos/Runner/Configs/Local.xcconfig.template` | Template for macOS signing |
| `macos/Runner/Configs/Local.xcconfig` | Your macOS signing config (gitignored) |
| `ios/Runner/Configs/Local.xcconfig.template` | Template for iOS signing |
| `ios/Runner/Configs/Local.xcconfig` | Your iOS signing config (gitignored) |
| `.gitignore` | Excludes `**/Local.xcconfig` |
