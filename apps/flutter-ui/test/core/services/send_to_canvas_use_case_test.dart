import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/canvas_content_service.dart';
import 'package:soliplex/core/services/canvas_service.dart';
import 'package:soliplex/core/services/send_to_canvas_use_case.dart';

class MockCanvasNotifier extends Mock implements CanvasNotifier {}

class MockCanvasContentService extends Mock implements CanvasContentService {}

void main() {
  group('SendToCanvasUseCase', () {
    late MockCanvasNotifier mockCanvasNotifier;
    late MockCanvasContentService mockContentService;
    late ProviderContainer container;

    setUp(() {
      mockCanvasNotifier = MockCanvasNotifier();
      mockContentService = MockCanvasContentService();
    });

    tearDown(() {
      container.dispose();
    });

    ProviderContainer createContainer({CanvasNotifier? canvasNotifier}) {
      return ProviderContainer(
        overrides: [
          activeCanvasNotifierProvider.overrideWithValue(canvasNotifier),
        ],
      );
    }

    group('execute with GenUI content', () {
      test('sends GenUI widget directly to canvas', () {
        container = createContainer(canvasNotifier: mockCanvasNotifier);
        final useCase = SendToCanvasUseCase(
          container.read(providerContainerProvider),
          contentService: mockContentService,
        );

        const genUiContent = GenUiContent(
          toolCallId: 'tool-123',
          widgetName: 'TestWidget',
          data: {'key': 'value'},
        );

        final result = useCase.execute(
          content: 'ignored',
          genUiContent: genUiContent,
        );

        expect(result, isA<SendToCanvasSuccess>());
        expect(
          (result as SendToCanvasSuccess).widgetName,
          equals('TestWidget'),
        );
        verify(
          () => mockCanvasNotifier.addItem('TestWidget', {'key': 'value'}),
        ).called(1);
        verifyNever(() => mockContentService.analyze(any()));
      });
    });

    group('execute with text content', () {
      test('analyzes text and sends to canvas', () {
        container = createContainer(canvasNotifier: mockCanvasNotifier);

        when(
          () => mockContentService.analyze(
            any(),
            sourceMessageId: any(named: 'sourceMessageId'),
          ),
        ).thenReturn(
          const CanvasContentAnalysis(
            type: CanvasContentType.plainText,
            widgetName: 'NoteCard',
            data: {'content': 'test content'},
          ),
        );

        final ref = container.read(providerContainerProvider);
        final useCase = SendToCanvasUseCase(
          ref,
          contentService: mockContentService,
        );

        final result = useCase.execute(
          content: 'test content',
          sourceMessageId: 'msg-123',
        );

        expect(result, isA<SendToCanvasSuccess>());
        expect((result as SendToCanvasSuccess).widgetName, equals('NoteCard'));
        verify(
          () => mockContentService.analyze(
            'test content',
            sourceMessageId: 'msg-123',
          ),
        ).called(1);
        verify(
          () => mockCanvasNotifier.addItem('NoteCard', {
            'content': 'test content',
          }),
        ).called(1);
      });

      test('returns failure for empty content', () {
        container = createContainer(canvasNotifier: mockCanvasNotifier);
        final ref = container.read(providerContainerProvider);
        final useCase = SendToCanvasUseCase(
          ref,
          contentService: mockContentService,
        );

        final result = useCase.execute(content: '');

        expect(result, isA<SendToCanvasFailure>());
        expect(
          (result as SendToCanvasFailure).error,
          equals('Content is empty'),
        );
        verifyNever(() => mockCanvasNotifier.addItem(any(), any()));
      });
    });

    group('error handling', () {
      test('returns failure when no active canvas', () {
        container = createContainer();
        final ref = container.read(providerContainerProvider);
        final useCase = SendToCanvasUseCase(
          ref,
          contentService: mockContentService,
        );

        final result = useCase.execute(content: 'test');

        expect(result, isA<SendToCanvasFailure>());
        expect(
          (result as SendToCanvasFailure).error,
          equals('No active canvas available'),
        );
      });

      test('returns failure on exception', () {
        container = createContainer(canvasNotifier: mockCanvasNotifier);

        when(
          () => mockContentService.analyze(
            any(),
            sourceMessageId: any(named: 'sourceMessageId'),
          ),
        ).thenThrow(Exception('Analysis failed'));

        final ref = container.read(providerContainerProvider);
        final useCase = SendToCanvasUseCase(
          ref,
          contentService: mockContentService,
        );

        final result = useCase.execute(content: 'test');

        expect(result, isA<SendToCanvasFailure>());
        expect(
          (result as SendToCanvasFailure).error,
          contains('Analysis failed'),
        );
      });
    });
  });

  group('SendToCanvasResult', () {
    test('SendToCanvasSuccess stores widget name', () {
      const result = SendToCanvasSuccess('TestWidget');
      expect(result.widgetName, equals('TestWidget'));
    });

    test('SendToCanvasFailure stores error message', () {
      const result = SendToCanvasFailure('Something went wrong');
      expect(result.error, equals('Something went wrong'));
    });
  });
}

/// Helper provider to get access to the container's ref
final providerContainerProvider = Provider<Ref>((ref) => ref);
