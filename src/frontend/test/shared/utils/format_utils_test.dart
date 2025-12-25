import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/shared/utils/format_utils.dart';

void main() {
  group('HttpTimestampFormat', () {
    group('toHttpTimeString', () {
      test('formats with zero padding', () {
        expect(DateTime(2024, 1, 1, 9, 5, 3).toHttpTimeString(), '09:05:03');
      });

      test('formats midnight correctly', () {
        expect(DateTime(2024).toHttpTimeString(), '00:00:00');
      });

      test('formats end of day correctly', () {
        expect(DateTime(2024, 1, 1, 23, 59, 59).toHttpTimeString(), '23:59:59');
      });

      test('formats double-digit values without extra padding', () {
        expect(DateTime(2024, 1, 1, 12, 34, 56).toHttpTimeString(), '12:34:56');
      });
    });
  });

  group('HttpDurationFormat', () {
    group('toHttpDurationString', () {
      test('formats milliseconds under 1 second', () {
        expect(
          const Duration(milliseconds: 45).toHttpDurationString(),
          '45ms',
        );
        expect(
          const Duration(milliseconds: 999).toHttpDurationString(),
          '999ms',
        );
        expect(Duration.zero.toHttpDurationString(), '0ms');
      });

      test('formats seconds under 1 minute', () {
        expect(const Duration(seconds: 1).toHttpDurationString(), '1.0s');
        expect(
          const Duration(milliseconds: 1500).toHttpDurationString(),
          '1.5s',
        );
        expect(const Duration(seconds: 59).toHttpDurationString(), '59.0s');
      });

      test('formats minutes for longer durations', () {
        expect(const Duration(minutes: 1).toHttpDurationString(), '1.0m');
        expect(const Duration(seconds: 90).toHttpDurationString(), '1.5m');
        expect(const Duration(minutes: 5).toHttpDurationString(), '5.0m');
      });

      test('boundary at 1 second', () {
        expect(
          const Duration(milliseconds: 999).toHttpDurationString(),
          '999ms',
        );
        expect(
          const Duration(milliseconds: 1000).toHttpDurationString(),
          '1.0s',
        );
      });

      test('boundary at 1 minute', () {
        expect(
          const Duration(milliseconds: 59999).toHttpDurationString(),
          '60.0s',
        );
        expect(
          const Duration(milliseconds: 60000).toHttpDurationString(),
          '1.0m',
        );
      });
    });
  });

  group('HttpBytesFormat', () {
    group('toHttpBytesString', () {
      test('formats bytes under 1KB', () {
        expect(0.toHttpBytesString(), '0B');
        expect(512.toHttpBytesString(), '512B');
        expect(1023.toHttpBytesString(), '1023B');
      });

      test('formats kilobytes under 1MB', () {
        expect(1024.toHttpBytesString(), '1.0KB');
        expect(1536.toHttpBytesString(), '1.5KB');
        expect((1024 * 1023).toHttpBytesString(), '1023.0KB');
      });

      test('formats megabytes for larger sizes', () {
        expect((1024 * 1024).toHttpBytesString(), '1.0MB');
        expect((1024 * 1024 * 5).toHttpBytesString(), '5.0MB');
        expect((1024 * 1024 + 512 * 1024).toHttpBytesString(), '1.5MB');
      });

      test('boundary at 1KB', () {
        expect(1023.toHttpBytesString(), '1023B');
        expect(1024.toHttpBytesString(), '1.0KB');
      });

      test('boundary at 1MB', () {
        expect((1024 * 1024 - 1).toHttpBytesString(), '1024.0KB');
        expect((1024 * 1024).toHttpBytesString(), '1.0MB');
      });
    });
  });
}
