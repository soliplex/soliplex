/// Constants for AG-UI event types used across the application.
///
/// Centralizes event type strings to prevent magic string issues and
/// ensure consistency.
class AgUiEventTypes {
  static const String runStarted = 'runStarted';
  static const String textMessageStart = 'TextMessageStart';
  static const String toolCallStart = 'ToolCallStart';
  static const String thinking = 'thinking';
  static const String runFinished = 'runFinished';
  static const String runError = 'runError';
  static const String activitySnapshot = 'activitySnapshot';
  static const String stateSnapshot = 'stateSnapshot';
  static const String stateDelta = 'stateDelta';
  static const String textMessage = 'textMessage';
  static const String toolResult = 'toolResult';
  static const String genUiRender = 'genUiRender';
  static const String userMessage = 'userMessage';
  static const String localToolExecution = 'localToolExecution';
}
