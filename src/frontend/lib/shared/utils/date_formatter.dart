/// Utility functions for formatting dates and times.
library;

/// Formats a [DateTime] as a relative time string.
///
/// Returns a human-readable string representing the time elapsed since
/// [dateTime]:
/// - "Just now" for times within 1 minute
/// - "X minutes ago" for times within 1 hour
/// - "X hours ago" for times within 1 day
/// - "X days ago" for times within 7 days
/// - "X weeks ago" for times within 4 weeks
/// - "X months ago" for times within 12 months
/// - "X years ago" for times beyond 1 year
///
/// Example:
/// ```dart
/// final now = DateTime.now();
/// final twoHoursAgo = now.subtract(Duration(hours: 2));
/// print(formatRelativeTime(twoHoursAgo)); // "2 hours ago"
/// ```
String formatRelativeTime(DateTime dateTime) {
  final now = DateTime.now();
  final difference = now.difference(dateTime);

  if (difference.inSeconds < 60) {
    return 'Just now';
  } else if (difference.inMinutes < 60) {
    final minutes = difference.inMinutes;
    return '$minutes ${minutes == 1 ? 'minute' : 'minutes'} ago';
  } else if (difference.inHours < 24) {
    final hours = difference.inHours;
    return '$hours ${hours == 1 ? 'hour' : 'hours'} ago';
  } else if (difference.inDays < 7) {
    final days = difference.inDays;
    return '$days ${days == 1 ? 'day' : 'days'} ago';
  } else if (difference.inDays < 30) {
    final weeks = (difference.inDays / 7).floor();
    return '$weeks ${weeks == 1 ? 'week' : 'weeks'} ago';
  } else if (difference.inDays < 365) {
    final months = (difference.inDays / 30).floor();
    return '$months ${months == 1 ? 'month' : 'months'} ago';
  } else {
    final years = (difference.inDays / 365).floor();
    return '$years ${years == 1 ? 'year' : 'years'} ago';
  }
}

/// Returns a short ID from a thread ID for display purposes.
///
/// Takes the last 8 characters of the ID, or the full ID if it's shorter.
///
/// Example:
/// ```dart
/// final id = 'thread-12345678-abcd-1234-5678-123456789abc';
/// print(getShortId(id)); // "6789abc"
/// ```
String getShortId(String id) {
  if (id.length <= 8) return id;
  return id.substring(id.length - 8);
}
