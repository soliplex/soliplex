import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/network/room_session.dart';
import 'package:soliplex/core/protocol/chat_session.dart';
import 'package:soliplex/core/providers/panel_providers.dart';

final slashCommandServiceProvider = Provider<SlashCommandService>((ref) {
  return SlashCommandService(ref);
});

typedef InputUpdateCallback = void Function(String text);
typedef GenUiEventCallback =
    void Function(
      String eventName,
      Map<String, dynamic> payload,
      InputUpdateCallback onInputUpdate,
    );

class SlashCommandService {
  SlashCommandService(this._ref);
  final Ref _ref;
  final Map<String, GenUiEventCallback> _searchCallbacks = {};

  /// Handle slash commands locally.
  /// Returns true if the command was handled.
  bool handleCommand(String text, ChatSession session) {
    // Slash commands currently rely on RoomSession features (GenUI, System
    // messages)
    if (session is! RoomSession) return false;

    final parts = text.split(' ');
    final command = parts[0].toLowerCase();
    final args = parts.skip(1).toList();

    switch (command) {
      case '/search':
        final searchType = args.isNotEmpty ? args[0] : 'items';
        _showSearchWidget(searchType, session);
        return true;

      case '/list':
        final listType = args.isNotEmpty ? args[0] : 'items';
        _showListWidget(listType, session);
        return true;

      case '/demo':
        final demoName = args.isNotEmpty ? args.join('-') : '';
        _showDemo(demoName, session);
        return true;

      case '/canvas':
        _showCanvasState(session);
        return true;

      case '/help':
        session.addSystemMessage(
          'Available commands:\n'
          '• /search staff - Search and select staff members\n'
          '• /list projects - Show available projects\n'
          '• /list demos - Show available demos\n'
          '• /demo <name> - Walk through a specific demo\n'
          '• /canvas - Show current canvas contents\n'
          '• /help - Show this help message',
        );
        return true;

      default:
        return false;
    }
  }

  /// Handle GenUI events (e.g., from search widgets).
  void handleGenUiEvent(
    String eventName,
    Map<String, Object?> arguments,
    InputUpdateCallback onInputUpdate,
  ) {
    final toolCallId = arguments['_toolCallId'] as String?;
    if (toolCallId != null && _searchCallbacks.containsKey(toolCallId)) {
      final callback = _searchCallbacks[toolCallId];
      final payload = Map<String, dynamic>.from(arguments);
      payload.remove('_toolCallId');
      callback?.call(eventName, payload, onInputUpdate);
    }
  }

  void _showSearchWidget(String searchType, RoomSession session) {
    session.addUserMessage('/search $searchType');

    List<Map<String, dynamic>> items;
    String placeholder;

    switch (searchType) {
      case 'staff':
        items = _stubbedStaffData;
        placeholder = 'Search staff by name or role...';
      default:
        items = _stubbedStaffData;
        placeholder = 'Search...';
    }

    final searchId = 'search-${DateTime.now().millisecondsSinceEpoch}';

    _searchCallbacks[searchId] = (eventName, payload, onInputUpdate) {
      _handleSearchWidgetEvent(
        eventName,
        payload,
        searchType,
        session,
        onInputUpdate,
      );
      if (eventName == 'submit' || eventName == 'cancel') {
        _searchCallbacks.remove(searchId);
      }
    };

    session.addGenUiMessage(
      GenUiContent(
        toolCallId: searchId,
        widgetName: 'SearchWidget',
        data: {
          '_toolCallId': searchId,
          'placeholder': placeholder,
          'multi_select': true,
          'items': items,
          'search_type': searchType,
        },
      ),
    );
  }

  void _showListWidget(String listType, RoomSession session) {
    session.addUserMessage('/list $listType');

    switch (listType) {
      case 'projects':
        for (final project in _stubbedProjectsData) {
          session.addGenUiMessage(
            GenUiContent(
              toolCallId:
                  // ignore: lines_longer_than_80_chars (auto-documented)
                  'project-${project['id']}-${DateTime.now().millisecondsSinceEpoch}',
              widgetName: 'ProjectCard',
              data: project,
            ),
          );
        }
      case 'demos':
        final demoList = _demos.entries
            .map((e) {
              final demo = e.value;
              return '• /demo ${e.key} - ${demo['title']}\n  ${demo['description']}';
            })
            .join('\n\n');
        session.addSystemMessage('Available Demos:\n\n$demoList');
      default:
        session.addSystemMessage(
          'Unknown list type: $listType\nTry: /list projects or /list demos',
        );
    }
  }

  void _showCanvasState(RoomSession session) {
    session.addUserMessage('/canvas');
    final canvasState = _ref.read(activeCanvasProvider);
    session.addSystemMessage(canvasState.toSummary());
  }

  void _showDemo(String demoName, RoomSession session) {
    session.addUserMessage('/demo $demoName');

    if (demoName.isEmpty) {
      session.addSystemMessage(
        'Usage: /demo <name>\nType /list demos to see available demos.',
      );
      return;
    }

    final demo = _demos[demoName];
    if (demo == null) {
      final available = _demos.keys.join(', ');
      session.addSystemMessage(
        'Unknown demo: $demoName\nAvailable: $available',
      );
      return;
    }

    final steps = (demo['steps'] as List<dynamic>).join('\n');
    session.addSystemMessage(
      '${demo['title']}\n'
      '${'-' * (demo['title'] as String).length}\n'
      '${demo['description']}\n\n'
      'Walkthrough:\n$steps',
    );
  }

  void _handleSearchWidgetEvent(
    String eventName,
    Map<String, dynamic> payload,
    String searchType,
    RoomSession session,
    InputUpdateCallback onInputUpdate,
  ) {
    switch (eventName) {
      case 'submit':
        final selected = payload['selected'] as List<dynamic>? ?? [];
        if (selected.isNotEmpty) {
          final names = selected
              .map((item) {
                final map = item as Map<String, dynamic>;
                return '${map['title']} (${map['subtitle']})';
              })
              .join(', ');

          final prefill = 'Selected $searchType: $names\n';
          onInputUpdate(prefill);
        }

      case 'cancel':
        session.addSystemMessage('Search cancelled.');
    }
  }

  // ===========================================================================
  // STUBBED DATA
  // ===========================================================================

  /// Stubbed staff data for /search staff command
  static const List<Map<String, dynamic>> _stubbedStaffData = [
    {'id': 'u1', 'title': 'John Smith', 'subtitle': 'Engineering Lead'},
    {'id': 'u2', 'title': 'Jane Doe', 'subtitle': 'Product Manager'},
    {'id': 'u3', 'title': 'Bob Wilson', 'subtitle': 'Senior Developer'},
    {'id': 'u4', 'title': 'Alice Johnson', 'subtitle': 'UX Designer'},
    {'id': 'u5', 'title': 'Charlie Brown', 'subtitle': 'DevOps Engineer'},
    {'id': 'u6', 'title': 'Diana Prince', 'subtitle': 'QA Lead'},
    {'id': 'u7', 'title': 'Edward Norton', 'subtitle': 'Backend Developer'},
    {'id': 'u8', 'title': 'Fiona Apple', 'subtitle': 'Frontend Developer'},
    {'id': 'u9', 'title': 'George Lucas', 'subtitle': 'Data Scientist'},
    {'id': 'u10', 'title': 'Hannah Montana', 'subtitle': 'Marketing Manager'},
  ];

  /// Stubbed projects data for /list projects command
  static const List<Map<String, dynamic>> _stubbedProjectsData = [
    {
      'id': 'p1',
      'title': 'Mobile App Redesign',
      'description':
          'Complete overhaul of the customer-facing mobile application',
      'required_skills': ['Flutter', 'Dart', 'Figma', 'UX Research'],
      'status': 'open',
    },
    {
      'id': 'p2',
      'title': 'Data Pipeline Migration',
      'description':
          'Migrate legacy ETL pipelines to cloud-native architecture',
      'required_skills': ['Python', 'AWS', 'Kubernetes', 'Docker'],
      'status': 'open',
    },
    {
      'id': 'p3',
      'title': 'ML Recommendation Engine',
      'description': 'Build personalized recommendation system for e-commerce',
      'required_skills': [
        'Python',
        'Machine Learning',
        'TensorFlow',
        'PostgreSQL',
      ],
      'status': 'open',
    },
  ];

  /// Demo definitions with walkthrough steps
  static const Map<String, Map<String, dynamic>> _demos = {
    'team-builder': {
      'title': 'Team Builder',
      'description':
          'Build an optimal team for a project based on required skills',
      'steps': [
        '1. Type: /list projects',
        '2. Pick a project (e.g., "Mobile App Redesign")',
        '3. Say: "Build me a team for the Mobile App Redesign project"',
      ],
    },
  };
}
