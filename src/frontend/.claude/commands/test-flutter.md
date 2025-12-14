Run Flutter tests for the soliplex_flutter client.

```bash
cd /Users/jaeminjo/enfold/afsoc-rag/src/soliplex/src/soliplex_flutter
flutter test
```

With coverage:
```bash
flutter test --coverage
lcov --summary coverage/lcov.info
```

Run specific test file:
```bash
flutter test test/<path>/test_file.dart
```
