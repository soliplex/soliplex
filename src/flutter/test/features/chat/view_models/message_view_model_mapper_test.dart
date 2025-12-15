import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/models/error_types.dart';
import 'package:soliplex/features/chat/view_models/chat_message_view_model.dart';
import 'package:soliplex/features/chat/view_models/message_view_model_mapper.dart';

void main() {
  group('MessageViewModelMapper', () {
    late MessageViewModelMapper mapper;

    setUp(() {
      mapper = MessageViewModelMapper();
    });

    test('maps TextMessage to TextMessageViewModel', () {
      final message =
          ChatMessage.text(
            id: 'msg1',
            user: ChatUser.user,
            text: 'Hello, world!',
            isStreaming: true,
          ).copyWith(
            thinkingText: 'thinking...',
            isThinkingStreaming: true,
            isThinkingExpanded: false,
          );

      final viewModel = mapper.map(message);

      expect(viewModel, isA<TextMessageViewModel>());
      expect(viewModel.id, equals(message.id));
      expect(viewModel.user, equals(message.user));
      expect(viewModel.createdAt, equals(message.createdAt));
      expect(viewModel.isUserMessage, isTrue);
      expect(viewModel.key, equals(ValueKey(message.id)));

      final textViewModel = viewModel as TextMessageViewModel;
      expect(textViewModel.text, equals('Hello, world!'));
      expect(textViewModel.isStreaming, isTrue);
      expect(textViewModel.thinkingText, equals('thinking...'));
      expect(textViewModel.isThinkingStreaming, isTrue);
      expect(textViewModel.isThinkingExpanded, isFalse);
    });

    test('maps Agent TextMessage to TextMessageViewModel', () {
      final message = ChatMessage.text(
        id: 'msg2',
        user: ChatUser.agent,
        text: 'Agent response',
      );

      final viewModel = mapper.map(message);

      expect(viewModel, isA<TextMessageViewModel>());
      expect(viewModel.isUserMessage, isFalse);
      final textViewModel = viewModel as TextMessageViewModel;
      expect(textViewModel.text, equals('Agent response'));
    });

    test('maps GenUiMessage to GenUiViewModel', () {
      const genUiContent = GenUiContent(
        toolCallId: 'tool1',
        widgetName: 'Card',
        data: {'value': 1},
      );
      final message = ChatMessage.genUi(
        id: 'msg3',
        user: ChatUser.agent,
        content: genUiContent,
      );

      final viewModel = mapper.map(message);

      expect(viewModel, isA<GenUiViewModel>());
      final genUiViewModel = viewModel as GenUiViewModel;
      expect(genUiViewModel.content, equals(genUiContent));
    });

    test('maps ErrorMessage to ErrorMessageViewModel', () {
      const errorInfo = ChatErrorInfo(
        type: ChatErrorType.server,
        friendlyMessage: 'Server connection failed',
        technicalDetails: 'Server down',
      );
      final message = ChatMessage.error(
        id: 'msg4',
        user: ChatUser.system,
        errorMessage: 'Connection failed',
        errorInfo: errorInfo,
      );

      final viewModel = mapper.map(message);

      expect(viewModel, isA<ErrorMessageViewModel>());
      final errorViewModel = viewModel as ErrorMessageViewModel;
      expect(errorViewModel.message, equals('Connection failed'));
      expect(errorViewModel.errorInfo, equals(errorInfo));
    });

    test('maps ToolCallMessage to ToolCallViewModel', () {
      final message = ChatMessage.toolCall(
        id: 'msg5',
        user: ChatUser.agent,
        toolName: 'search_db',
      );

      final viewModel = mapper.map(message);

      expect(viewModel, isA<ToolCallViewModel>());
      final toolViewModel = viewModel as ToolCallViewModel;
      expect(toolViewModel.toolCallName, equals('search_db'));
      expect(toolViewModel.status, equals('executing'));
    });

    test('maps ToolCallGroupMessage to ToolCallGroupViewModel', () {
      final toolCallSummary = [
        ToolCallSummary(
          toolCallId: 'tcs1',
          toolName: 'tool',
          status: ToolCallStatus.executing,
          startedAt: DateTime.now(),
        ),
      ];
      final message = ChatMessage.toolCallGroup(
        id: 'msg6',
        user: ChatUser.agent,
        toolCalls: toolCallSummary,
        isExpanded: true,
      );

      final viewModel = mapper.map(message);

      expect(viewModel, isA<ToolCallGroupViewModel>());
      final groupViewModel = viewModel as ToolCallGroupViewModel;
      expect(groupViewModel.toolCalls, equals(toolCallSummary));
      expect(groupViewModel.isExpanded, isTrue);
    });

    test('maps LoadingMessage to LoadingMessageViewModel', () {
      final message = ChatMessage.loading(id: 'msg7', user: ChatUser.agent);

      final viewModel = mapper.map(message);

      expect(viewModel, isA<LoadingMessageViewModel>());
    });

    test(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'maps GenUiMessage with null content gracefully (returns ErrorMessageViewModel)', // ignore: lines_longer_than_80_chars
      () {
        final message = ChatMessage(
          id: 'msg8',
          user: ChatUser.agent,
          type: MessageType.genUi,
        );

        final viewModel = mapper.map(message);

        expect(viewModel, isA<ErrorMessageViewModel>());
        final errorViewModel = viewModel as ErrorMessageViewModel;
        expect(errorViewModel.message, equals('GenUI content missing'));
      },
    );
  });
}
