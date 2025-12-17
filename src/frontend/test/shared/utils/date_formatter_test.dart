import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/shared/utils/date_formatter.dart';

void main() {
  group('formatRelativeTime', () {
    test('returns "Just now" for times within 1 minute', () {
      final now = DateTime.now();
      final thirtySecondsAgo = now.subtract(const Duration(seconds: 30));
      expect(formatRelativeTime(thirtySecondsAgo), 'Just now');
    });

    test('returns "X minutes ago" for times within 1 hour', () {
      final now = DateTime.now();
      final twoMinutesAgo = now.subtract(const Duration(minutes: 2));
      expect(formatRelativeTime(twoMinutesAgo), '2 minutes ago');

      final oneMinuteAgo = now.subtract(const Duration(minutes: 1));
      expect(formatRelativeTime(oneMinuteAgo), '1 minute ago');
    });

    test('returns "X hours ago" for times within 1 day', () {
      final now = DateTime.now();
      final twoHoursAgo = now.subtract(const Duration(hours: 2));
      expect(formatRelativeTime(twoHoursAgo), '2 hours ago');

      final oneHourAgo = now.subtract(const Duration(hours: 1));
      expect(formatRelativeTime(oneHourAgo), '1 hour ago');
    });

    test('returns "X days ago" for times within 1 week', () {
      final now = DateTime.now();
      final twoDaysAgo = now.subtract(const Duration(days: 2));
      expect(formatRelativeTime(twoDaysAgo), '2 days ago');

      final oneDayAgo = now.subtract(const Duration(days: 1));
      expect(formatRelativeTime(oneDayAgo), '1 day ago');
    });

    test('returns "X weeks ago" for times within 1 month', () {
      final now = DateTime.now();
      final twoWeeksAgo = now.subtract(const Duration(days: 14));
      expect(formatRelativeTime(twoWeeksAgo), '2 weeks ago');

      final oneWeekAgo = now.subtract(const Duration(days: 7));
      expect(formatRelativeTime(oneWeekAgo), '1 week ago');
    });

    test('returns "X months ago" for times within 1 year', () {
      final now = DateTime.now();
      final twoMonthsAgo = now.subtract(const Duration(days: 60));
      expect(formatRelativeTime(twoMonthsAgo), '2 months ago');

      final oneMonthAgo = now.subtract(const Duration(days: 30));
      expect(formatRelativeTime(oneMonthAgo), '1 month ago');
    });

    test('returns "X years ago" for times beyond 1 year', () {
      final now = DateTime.now();
      final twoYearsAgo = now.subtract(const Duration(days: 730));
      expect(formatRelativeTime(twoYearsAgo), '2 years ago');

      final oneYearAgo = now.subtract(const Duration(days: 365));
      expect(formatRelativeTime(oneYearAgo), '1 year ago');
    });
  });

  group('getShortId', () {
    test('returns last 8 characters for long IDs', () {
      const longId = 'thread-12345678-abcd-1234-5678-123456789abc';
      expect(getShortId(longId), '56789abc');
    });

    test('returns full ID for short IDs', () {
      const shortId = 'abc123';
      expect(getShortId(shortId), 'abc123');
    });

    test('returns full ID for exactly 8 character IDs', () {
      const exactId = '12345678';
      expect(getShortId(exactId), '12345678');
    });
  });
}
