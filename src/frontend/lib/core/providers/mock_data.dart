import 'package:soliplex_client/soliplex_client.dart';

/// Hardcoded mock data for AM1 development.
///
/// **DELETE THIS FILE IN AM2** when connecting to real backend.
class MockData {
  const MockData._();

  /// Mock rooms for testing navigation and UI.
  static final rooms = [
    const Room(
      id: 'general',
      name: 'General Chat',
      description: 'General purpose RAG queries and conversations',
    ),
    const Room(
      id: 'technical',
      name: 'Technical Support',
      description: 'Technical documentation and troubleshooting',
    ),
    const Room(
      id: 'research',
      name: 'Research & Analysis',
      description: 'Deep research queries and analysis',
    ),
  ];

  /// Mock threads per room.
  static final threads = <String, List<ThreadInfo>>{
    'general': [
      ThreadInfo(
        id: 'thread-g1',
        roomId: 'general',
        name: 'How does RAG work?',
        createdAt: DateTime(2025, 1, 2, 10, 30),
      ),
      ThreadInfo(
        id: 'thread-g2',
        roomId: 'general',
        name: 'System architecture overview',
        createdAt: DateTime(2025, 1, 2, 14, 15),
      ),
      ThreadInfo(
        id: 'thread-g3',
        roomId: 'general',
        name: 'Getting started guide',
        createdAt: DateTime(2025, 1, 3, 9),
      ),
      ThreadInfo(
        id: 'thread-g4',
        roomId: 'general',
        name: 'Best practices for queries',
        createdAt: DateTime(2025, 1, 3, 16, 45),
      ),
      ThreadInfo(
        id: 'thread-g5',
        roomId: 'general',
        name: 'Common issues and solutions',
        createdAt: DateTime(2025, 1, 4, 11, 20),
      ),
    ],
    'technical': [
      ThreadInfo(
        id: 'thread-t1',
        roomId: 'technical',
        name: 'API authentication issues',
        createdAt: DateTime(2025, 1, 2, 11),
      ),
      ThreadInfo(
        id: 'thread-t2',
        roomId: 'technical',
        name: 'Database connection errors',
        createdAt: DateTime(2025, 1, 2, 15, 30),
      ),
      ThreadInfo(
        id: 'thread-t3',
        roomId: 'technical',
        name: 'Performance optimization',
        createdAt: DateTime(2025, 1, 3, 10, 15),
      ),
      ThreadInfo(
        id: 'thread-t4',
        roomId: 'technical',
        name: 'Deployment configuration',
        createdAt: DateTime(2025, 1, 4, 14),
      ),
    ],
    'research': [
      ThreadInfo(
        id: 'thread-r1',
        roomId: 'research',
        name: 'Market analysis Q1 2025',
        createdAt: DateTime(2025, 1, 2, 9, 30),
      ),
      ThreadInfo(
        id: 'thread-r2',
        roomId: 'research',
        name: 'Competitor feature comparison',
        createdAt: DateTime(2025, 1, 3, 13, 45),
      ),
      ThreadInfo(
        id: 'thread-r3',
        roomId: 'research',
        name: 'User research insights',
        createdAt: DateTime(2025, 1, 4, 10),
      ),
      ThreadInfo(
        id: 'thread-r4',
        roomId: 'research',
        name: 'Technology trends 2025',
        createdAt: DateTime(2025, 1, 4, 15, 30),
      ),
      ThreadInfo(
        id: 'thread-r5',
        roomId: 'research',
        name: 'ROI analysis framework',
        createdAt: DateTime(2025, 1, 5, 11, 15),
      ),
    ],
  };
}
