import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/providers/canvas_provider.dart';

void main() {
  group('CanvasStateNotifier', () {
    late CanvasStateNotifier notifier;

    setUp(() {
      notifier = CanvasStateNotifier();
    });

    test('initial state is empty map', () {
      expect(notifier.state, isEmpty);
    });

    test('updateState replaces entire state', () {
      notifier.updateState({'key': 'value', 'count': 1});

      expect(notifier.state, equals({'key': 'value', 'count': 1}));

      notifier.updateState({'newKey': 'newValue'});

      expect(notifier.state, equals({'newKey': 'newValue'}));
      expect(notifier.state.containsKey('key'), isFalse);
    });

    test('applyDelta merges with existing state', () {
      notifier.updateState({'a': 1, 'b': 2});
      notifier.applyDelta({'b': 3, 'c': 4});

      expect(notifier.state, equals({'a': 1, 'b': 3, 'c': 4}));
    });

    test('clear resets to empty map', () {
      notifier.updateState({'key': 'value'});
      notifier.clear();

      expect(notifier.state, isEmpty);
    });

    test('getValue returns value for key', () {
      notifier.updateState({'name': 'test', 'count': 42});

      expect(notifier.getValue('name'), equals('test'));
      expect(notifier.getValue('count'), equals(42));
      expect(notifier.getValue('missing'), isNull);
    });

    test('setValue sets single key', () {
      notifier.updateState({'existing': 'value'});
      notifier.setValue('newKey', 'newValue');

      expect(notifier.state['newKey'], equals('newValue'));
      expect(notifier.state['existing'], equals('value'));
    });
  });

  group('canvasStateProvider', () {
    test('provides CanvasStateNotifier', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final state = container.read(canvasStateProvider);
      expect(state, isA<Map<String, dynamic>>());
      expect(state, isEmpty);
    });

    test('notifier updates reflect in state', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final notifier = container.read(canvasStateProvider.notifier);
      notifier.updateState({'test': 'data'});

      final state = container.read(canvasStateProvider);
      expect(state, equals({'test': 'data'}));
    });
  });

  group('isAgentActiveProvider', () {
    test('initial state is false', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final isActive = container.read(isAgentActiveProvider);
      expect(isActive, isFalse);
    });

    test('can toggle state', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(isAgentActiveProvider.notifier).state = true;
      expect(container.read(isAgentActiveProvider), isTrue);

      container.read(isAgentActiveProvider.notifier).state = false;
      expect(container.read(isAgentActiveProvider), isFalse);
    });
  });
}
