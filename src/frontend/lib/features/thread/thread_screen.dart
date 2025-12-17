import 'package:flutter/material.dart';

/// Placeholder screen for thread chat view.
///
/// Chat functionality implemented in AM3.
class ThreadScreen extends StatelessWidget {
  const ThreadScreen({
    required this.roomId,
    required this.threadId,
    super.key,
  });

  final String roomId;
  final String threadId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Thread'),
      ),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.chat,
              size: 64,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'Chat UI - Coming in AM3',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Room: $roomId\nThread: $threadId',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}
