# Making SOLIPLEX Flutter Frontend Reusable

This document outlines three levels of increasingly sophisticated integration for making the Flutter frontend reusable as a white-label/templatable solution.

## Overview

The goal is to allow consumers to:
- Wire in custom panels
- Add custom slash commands
- Register custom widgets
- Configure deep linking
- Apply their own branding

---

## Level 1: Configuration-Driven Customization

**Effort: Low | Flexibility: Limited**

A consumer provides a configuration object at app startup - no code changes required.

### What They Can Customize

- **Branding**: App name, colors, logo, theme
- **Feature flags**: Enable/disable panels (canvas, context pane, inspector)
- **Default routes**: Initial screen, available navigation items
- **Pre-registered servers**: Default server URLs, OIDC providers

### Implementation Pattern

```dart
// Consumer's main.dart
void main() {
  runSoliplexApp(
    SoliplexConfig(
      appName: 'MyChat',
      theme: MyTheme.data,
      features: Features(
        enableCanvas: true,
        enableContextPane: false,
        enableInspector: false,
      ),
      routes: RouteConfig(
        initialRoute: '/chat',
        hideSettings: true,
      ),
      defaultServers: [
        ServerConfig(url: 'https://api.mycompany.com', name: 'Production'),
      ],
    ),
  );
}
```

### Changes Required

| Area | Change |
|------|--------|
| `main.dart` | Accept `SoliplexConfig` parameter |
| `app_shell.dart` | Read config from provider, apply theme |
| `app_router.dart` | Filter routes based on `RouteConfig` |
| Layouts | Conditionally render panels based on `Features` |

### Limitations

- No custom panels or widgets
- No custom slash commands
- Fixed UI structure

---

## Level 2: Registry-Based Extension

**Effort: Medium | Flexibility: Moderate**

Consumer registers custom components via typed registries at startup.

### What They Can Customize

Everything from Level 1, plus:
- **Custom GenUI widgets**: Register new widget builders
- **Custom slash commands**: Add command handlers
- **Custom panels**: Register panel providers with layouts
- **Custom keyboard shortcuts**: Add app-wide shortcuts
- **Deep link handlers**: Custom route handlers

### Implementation Pattern

```dart
void main() {
  final registry = SoliplexRegistry()
    // Custom widgets
    ..registerWidget('CompanyCard', CompanyCardWidget.fromData)
    ..registerWidget('OrgChart', OrgChartWidget.fromData)

    // Custom slash commands
    ..registerCommand(SlashCommand(
      name: 'ticket',
      description: 'Create support ticket',
      handler: (args, session) => _handleTicket(args, session),
    ))

    // Custom panel
    ..registerPanel(PanelDefinition(
      id: 'tickets',
      name: 'Support Tickets',
      icon: Icons.confirmation_number,
      builder: (context, ref) => TicketPanel(),
      providerFactory: (key) => ticketPanelProvider(key),
    ))

    // Custom routes
    ..registerRoute(RouteDefinition(
      path: '/tickets/:id',
      builder: (context, state) => TicketDetailScreen(
        id: state.pathParameters['id']!,
      ),
    ));

  runSoliplexApp(
    config: SoliplexConfig(...),
    registry: registry,
  );
}
```

### New Abstractions Required

```dart
// lib/core/extension/slash_command.dart
class SlashCommand {
  final String name;
  final String description;
  final bool Function(List<String> args, RoomSession session) handler;
}

// lib/core/extension/panel_definition.dart
class PanelDefinition {
  final String id;
  final String name;
  final IconData icon;
  final Widget Function(BuildContext, WidgetRef) builder;
  final ProviderBase Function(ServerRoomKey) providerFactory;
  final PanelPosition defaultPosition; // left, right, bottom
}

// lib/core/extension/route_definition.dart
class RouteDefinition {
  final String path;
  final Widget Function(BuildContext, GoRouterState) builder;
  final List<RouteDefinition> children;
}
```

### Changes Required

| Area | Change |
|------|--------|
| `widget_registry.dart` | Already extensible, expose via registry |
| `slash_command_service.dart` | Switch from hardcoded switch to registered handlers |
| `panel_providers.dart` | Dynamic provider registration |
| `app_router.dart` | Merge registered routes with core routes |
| Layouts | Query registry for available panels |
| Navigation drawer | Render registered panels dynamically |

---

## Level 3: Full Plugin Architecture

**Effort: High | Flexibility: Maximum**

Consumers build self-contained plugins that integrate via lifecycle hooks and can modify core behavior.

### What They Can Customize

Everything from Levels 1 & 2, plus:
- **Message interceptors**: Transform/filter messages before display
- **Event hooks**: React to app lifecycle events
- **Protocol extensions**: Custom message types, tool handlers
- **State middleware**: Intercept and transform state changes
- **Custom layouts**: Entirely new screen arrangements
- **Theme extensions**: Beyond colors - custom widget variants

### Implementation Pattern

```dart
// my_company_plugin/lib/plugin.dart
class MyCompanyPlugin extends SoliplexPlugin {
  @override
  String get id => 'com.mycompany.chat';

  @override
  List<SoliplexPlugin> get dependencies => [AnalyticsPlugin()];

  @override
  void register(PluginContext context) {
    // Register all extensions
    context.widgets.register('CompanyCard', CompanyCard.fromData);
    context.commands.register(TicketCommand());
    context.panels.register(TicketPanelPlugin());
    context.routes.register('/tickets', TicketRoutes());
  }

  @override
  void onAppStart(AppLifecycleContext context) {
    // Initialize plugin state
    _analyticsService = context.ref.read(analyticsProvider);
  }

  @override
  void onServerConnect(ServerContext context) {
    // Hook into server connection
    _trackServerConnection(context.serverUrl);
  }

  @override
  MessageInterceptor? get messageInterceptor => _MessageEnricher();

  @override
  List<ProviderOverride> get providerOverrides => [
    // Override core providers if needed
    feedbackServiceProvider.overrideWith((ref) => MyFeedbackService()),
  ];
}

// Message interceptor example
class _MessageEnricher implements MessageInterceptor {
  @override
  UnifiedMessage? intercept(UnifiedMessage message, InterceptContext ctx) {
    // Add company-specific metadata
    if (message.isFromAgent) {
      return message.copyWith(
        metadata: {...message.metadata, 'processed': true},
      );
    }
    return message;
  }
}
```

### Plugin Lifecycle

```text
┌─────────────────────────────────────────────────────────┐
│                    App Startup                          │
├─────────────────────────────────────────────────────────┤
│  1. Load plugin manifests                               │
│  2. Resolve dependencies (topological sort)             │
│  3. Call plugin.register() for each                     │
│  4. Build merged router, registries                     │
│  5. Call plugin.onAppStart()                            │
├─────────────────────────────────────────────────────────┤
│                   Runtime Events                        │
├─────────────────────────────────────────────────────────┤
│  • onServerConnect(ctx)    - Server selected            │
│  • onRoomJoin(ctx)         - Room entered               │
│  • onMessageReceive(msg)   - Before message displayed   │
│  • onMessageSend(msg)      - Before message sent        │
│  • onToolCall(call)        - Tool execution started     │
│  • onError(error, stack)   - Error occurred             │
├─────────────────────────────────────────────────────────┤
│                     Shutdown                            │
├─────────────────────────────────────────────────────────┤
│  • onAppStop()             - Cleanup opportunity        │
└─────────────────────────────────────────────────────────┘
```

### New Core Abstractions

```dart
// lib/core/plugin/soliplex_plugin.dart
abstract class SoliplexPlugin {
  String get id;
  String get version => '1.0.0';
  List<SoliplexPlugin> get dependencies => [];

  void register(PluginContext context);

  // Lifecycle hooks (all optional)
  void onAppStart(AppLifecycleContext context) {}
  void onAppStop() {}
  void onServerConnect(ServerContext context) {}
  void onServerDisconnect(ServerContext context) {}
  void onRoomJoin(RoomContext context) {}
  void onRoomLeave(RoomContext context) {}
  void onError(Object error, StackTrace stack) {}

  // Interceptors (optional)
  MessageInterceptor? get messageInterceptor => null;
  ToolCallInterceptor? get toolCallInterceptor => null;

  // Provider overrides (optional)
  List<ProviderOverride> get providerOverrides => [];
}

// lib/core/plugin/plugin_context.dart
class PluginContext {
  final WidgetRegistry widgets;
  final CommandRegistry commands;
  final PanelRegistry panels;
  final RouteRegistry routes;
  final ShortcutRegistry shortcuts;
  final LayoutRegistry layouts;
  final ThemeExtensions themes;
}
```

### Package Structure for Consumers

```text
my_app/
├── lib/
│   ├── main.dart              # App entry point
│   ├── config.dart            # SoliplexConfig
│   └── plugins/
│       ├── branding/          # Theme, logos
│       ├── analytics/         # Event tracking
│       └── domain/            # Business-specific features
├── pubspec.yaml
│   dependencies:
│     soliplex_core: ^1.0.0    # Core framework (this repo)
│     soliplex_widgets: ^1.0.0 # Optional widget pack
```

---

## Comparison Summary

| Capability | Level 1 | Level 2 | Level 3 |
|------------|---------|---------|---------|
| Custom branding/theme | Yes | Yes | Yes |
| Feature toggles | Yes | Yes | Yes |
| Custom widgets | No | Yes | Yes |
| Custom slash commands | No | Yes | Yes |
| Custom panels | No | Yes | Yes |
| Custom routes | No | Yes | Yes |
| Message interceptors | No | No | Yes |
| Lifecycle hooks | No | No | Yes |
| Provider overrides | No | No | Yes |
| Plugin dependencies | No | No | Yes |
| Custom layouts | No | Limited | Yes |
| Implementation effort | Low | Medium | High |

---

## Current Architecture Reference

The following existing patterns inform this design:

### Panel System
- **Location**: `lib/core/providers/panel_providers.dart`
- **Pattern**: Server-scoped notifiers with `.family` providers keyed by `ServerRoomKey`
- **Existing panels**: Canvas, Context Pane, Activity Status, Tool Execution, Message Stream

### Widget Registry
- **Location**: `lib/core/services/widget_registry.dart`
- **Pattern**: Name-to-builder mapping, already extensible via `register()` method
- **Existing widgets**: InfoCard, MetricDisplay, DataList, SearchWidget, etc.

### Slash Commands
- **Location**: `lib/features/chat/services/slash_command_service.dart`
- **Pattern**: Currently hardcoded switch statement - needs refactoring for Level 2+
- **Existing commands**: /search, /list, /demo, /canvas, /help

### Routing
- **Location**: `lib/core/router/app_router.dart`
- **Pattern**: GoRouter with shell route, auth guard redirect
- **Existing routes**: /setup, /auth/callback, /chat, /chat/:roomId, /settings, /inspector

### Configuration
- **Location**: `lib/main.dart`, `lib/app_shell.dart`
- **Pattern**: Runtime-driven via providers, no external config files currently

---

## Recommended Approach

Start with **Level 2** as the target architecture:
1. It provides meaningful extensibility without over-engineering
2. The registry pattern aligns with existing `WidgetRegistry` design
3. Plugin lifecycle (Level 3) can be added later if demand exists
4. Level 1 falls out naturally as a subset of Level 2

### Implementation Order

1. Define `SoliplexConfig` and `SoliplexRegistry` interfaces
2. Refactor `SlashCommandService` to use registered handlers
3. Create `PanelRegistry` abstraction
4. Extend `app_router.dart` to accept route definitions
5. Update layouts to query registries dynamically
6. Extract core into `soliplex_core` package
