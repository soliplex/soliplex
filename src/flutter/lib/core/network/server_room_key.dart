// reason: mutable data class pattern
// ignore_for_file: avoid_equals_and_hash_code_on_mutable_classes
/// Composite key for uniquely identifying a room across servers.
///
/// Used throughout the multi-connection architecture to scope state
/// to a specific server+room combination.
///
/// Two keys are equal if and only if both [serverId] and [roomId] match.
class ServerRoomKey {
  /// Creates a new server-room key.
  ///
  /// Both [serverId] and [roomId] must be non-empty strings.
  const ServerRoomKey({required this.serverId, required this.roomId});

  /// Creates a key from a colon-separated string (e.g., "server1:room1").
  ///
  /// Throws FormatException if the string is not in the expected format.
  factory ServerRoomKey.parse(String key) {
    final colonIndex = key.indexOf(':');
    if (colonIndex == -1 || colonIndex == 0 || colonIndex == key.length - 1) {
      throw FormatException(
        'Invalid ServerRoomKey format: "$key". Expected "serverId:roomId"',
      );
    }
    return ServerRoomKey(
      serverId: key.substring(0, colonIndex),
      roomId: key.substring(colonIndex + 1),
    );
  }

  /// The server identifier (typically from ServerConnection.id).
  final String serverId;

  /// The room identifier within the server.
  final String roomId;

  /// Whether this key has valid (non-empty) components.
  bool get isValid => serverId.isNotEmpty && roomId.isNotEmpty;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ServerRoomKey &&
          runtimeType == other.runtimeType &&
          serverId == other.serverId &&
          roomId == other.roomId;

  @override
  int get hashCode => Object.hash(serverId, roomId);

  @override
  String toString() => '$serverId:$roomId';

  /// Creates a copy with optionally updated fields.
  ServerRoomKey copyWith({String? serverId, String? roomId}) {
    return ServerRoomKey(
      serverId: serverId ?? this.serverId,
      roomId: roomId ?? this.roomId,
    );
  }
}
