import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/network/room_session.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/canvas_service.dart';
import 'package:soliplex/features/chat/services/slash_command_service.dart';

// Mocks
class MockRef extends Mock implements Ref {}

class MockRoomSession extends Mock implements RoomSession {}

class MockCanvasState extends Mock implements CanvasState {}

class FakeGenUiContent extends Fake implements GenUiContent {}

void main() {
  group('SlashCommandService', () {
    late MockRef mockRef;
    late MockRoomSession mockRoomSession;
    late MockCanvasState mockCanvasState;
    late SlashCommandService slashCommandService;

    setUpAll(() {
      registerFallbackValue(FakeGenUiContent());
    });

    setUp(() {
      mockRef = MockRef();
      mockRoomSession = MockRoomSession();
      mockCanvasState = MockCanvasState();

      when(
        () => mockRef.read(activeCanvasProvider),
      ).thenReturn(mockCanvasState);
      when(() => mockCanvasState.toSummary()).thenReturn('Canvas Summary');
      when(() => mockRoomSession.addUserMessage(any())).thenReturn(null);
      when(() => mockRoomSession.addSystemMessage(any())).thenReturn(null);
      when(() => mockRoomSession.addGenUiMessage(any())).thenReturn(null);

      slashCommandService = SlashCommandService(mockRef);
    });

    tearDown(() {
      reset(mockRef);
      reset(mockRoomSession);
      reset(mockCanvasState);
    });

    group('handleCommand', () {
      test(
        '/search command calls session.addUserMessage and session.addGenUiMessage', // ignore: lines_longer_than_80_chars (auto-documented)
        () {
          const commandText = '/search staff';
          final handled = slashCommandService.handleCommand(
            commandText,
            mockRoomSession,
          );

          expect(handled, isTrue);
          verify(() => mockRoomSession.addUserMessage(commandText)).called(1);
          verify(
            () => mockRoomSession.addGenUiMessage(
              any(
                that: isA<GenUiContent>().having(
                  (g) => g.widgetName,
                  'widgetName',
                  'SearchWidget',
                ),
              ),
            ),
          ).called(1);
        },
      );

      test(
        '/list projects command calls session.addUserMessage and multiple session.addGenUiMessage', // ignore: lines_longer_than_80_chars (auto-documented)
        () {
          const commandText = '/list projects';
          final handled = slashCommandService.handleCommand(
            commandText,
            mockRoomSession,
          );

          expect(handled, isTrue);
          verify(() => mockRoomSession.addUserMessage(commandText)).called(1);
          verify(
            () => mockRoomSession.addGenUiMessage(
              any(
                that: isA<GenUiContent>().having(
                  (g) => g.widgetName,
                  'widgetName',
                  'ProjectCard',
                ),
              ),
            ),
          ).called(3); // 3 stubbed projects
        },
      );

      test(
        '/list demos command calls session.addUserMessage and session.addSystemMessage', // ignore: lines_longer_than_80_chars (auto-documented)
        () {
          const commandText = '/list demos';
          final handled = slashCommandService.handleCommand(
            commandText,
            mockRoomSession,
          );

          expect(handled, isTrue);
          verify(() => mockRoomSession.addUserMessage(commandText)).called(1);
          verify(
            () => mockRoomSession.addSystemMessage(
              any(that: contains('Available Demos:')),
            ),
          ).called(1);
        },
      );

      test(
        '/demo command calls session.addUserMessage and session.addSystemMessage', // ignore: lines_longer_than_80_chars (auto-documented)
        () {
          const commandText = '/demo team-builder';
          final handled = slashCommandService.handleCommand(
            commandText,
            mockRoomSession,
          );

          expect(handled, isTrue);
          verify(() => mockRoomSession.addUserMessage(commandText)).called(1);
          verify(
            () => mockRoomSession.addSystemMessage(
              any(that: contains('Team Builder')),
            ),
          ).called(1);
        },
      );

      test(
        '/canvas command calls session.addUserMessage and session.addSystemMessage', // ignore: lines_longer_than_80_chars (auto-documented)
        () {
          const commandText = '/canvas';
          final handled = slashCommandService.handleCommand(
            commandText,
            mockRoomSession,
          );

          expect(handled, isTrue);
          verify(() => mockRoomSession.addUserMessage(commandText)).called(1);
          verify(
            () => mockRoomSession.addSystemMessage('Canvas Summary'),
          ).called(1);
        },
      );

      test('/help command calls session.addSystemMessage', () {
        const commandText = '/help';
        final handled = slashCommandService.handleCommand(
          commandText,
          mockRoomSession,
        );

        expect(handled, isTrue);
        verify(
          () => mockRoomSession.addSystemMessage(
            any(that: contains('Available commands:')),
          ),
        ).called(1);
      });

      test('unhandled command returns false', () {
        const commandText = '/unknown';
        final handled = slashCommandService.handleCommand(
          commandText,
          mockRoomSession,
        );

        expect(handled, isFalse);
        verifyNever(() => mockRoomSession.addUserMessage(any()));
        verifyNever(() => mockRoomSession.addSystemMessage(any()));
      });
    });

    group('handleGenUiEvent', () {
      test(
        'calls registered callback and updates input for submit event',
        () async {
          // Simulate a /search command to register a callback
          slashCommandService.handleCommand('/search staff', mockRoomSession);

          // Capture the generated toolCallId
          final captured = verify(
            () => mockRoomSession.addGenUiMessage(captureAny()),
          ).captured;
          final genUiContent = captured.first as GenUiContent;
          final toolCallId = genUiContent.toolCallId;

          String? updatedInputText;
          void onInputUpdate(String text) {
            updatedInputText = text;
          }

          await Future.microtask(() {});

          slashCommandService.handleGenUiEvent('submit', {
            '_toolCallId': toolCallId,
            'selected': [
              {'title': 'John', 'subtitle': 'Eng'},
            ],
          }, onInputUpdate);

          expect(updatedInputText, 'Selected staff: John (Eng)\n');
        },
      );

      test(
        'calls registered callback and adds system message for cancel event',
        () async {
          // Simulate a /search command to register a callback
          slashCommandService.handleCommand('/search staff', mockRoomSession);

          // Capture the generated toolCallId
          final captured = verify(
            () => mockRoomSession.addGenUiMessage(captureAny()),
          ).captured;
          final genUiContent = captured.first as GenUiContent;
          final toolCallId = genUiContent.toolCallId;

          void onInputUpdate(String text) {
            /* no-op */
          }

          await Future.microtask(() {});

          slashCommandService.handleGenUiEvent('cancel', {
            '_toolCallId': toolCallId,
          }, onInputUpdate);

          verify(
            () => mockRoomSession.addSystemMessage('Search cancelled.'),
          ).called(1);
        },
      );

      test('does nothing if toolCallId is null or no callback registered', () {
        // No initial setup means no callbacks are registered

        slashCommandService.handleGenUiEvent('submit', {
          'selected': [
            {'title': 'John', 'subtitle': 'Eng'},
          ],
        }, (text) {});
        slashCommandService.handleGenUiEvent('submit', {
          '_toolCallId': 'non-existent-id',
          'selected': [
            {'title': 'John', 'subtitle': 'Eng'},
          ],
        }, (text) {});

        verifyZeroInteractions(mockRoomSession);
      });
    });
  });
}
