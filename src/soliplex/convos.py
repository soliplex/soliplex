"""Track converstations by user and room.

If / when we move to a "persistent" history store, this module should firewall
that choice away from the rest of the system.
"""
import asyncio
import dataclasses
import typing
import uuid

import fastapi
import typing_extensions
from pydantic_ai import messages as ai_messages

REQUEST_CONTEXT_PARTS = ("system-prompt", "user-prompt")
RESPONSE_CONTEXT_PARTS = ("text", )


#==============================================================================
#   Impedance matching helpers for different message schemas
#==============================================================================

class _ConvoMessage(typing_extensions.TypedDict):
    """Format of messages streamed to the client during a conversation."""
    role: typing.Literal["user", "model"]
    timestamp: str
    content: str


def _to_convo_message(m: ai_messages.ModelMessage) -> _ConvoMessage | None:
    for part in m.parts:
        if isinstance(m, ai_messages.ModelRequest):
            if isinstance(part, ai_messages.UserPromptPart):
                assert isinstance(part.content, str)
                return {
                    "role": "user",
                    "timestamp": part.timestamp.isoformat(),
                    "content": part.content,
                }
        elif isinstance(m, ai_messages.ModelResponse):
            if isinstance(part, ai_messages.TextPart):
                return {
                    "role": "model",
                    "timestamp": m.timestamp.isoformat(),
                    "content": part.content,
                }
            elif isinstance(part, ai_messages.ThinkingPart):
                continue
            elif isinstance(part, ai_messages.ToolCallPart):
                continue
            else:  # pragma: NO COVER suppress spurious branch miss
                pass
        else:  # pragma: NO COVER suppress spurious branch miss
            pass
    # Return None for messages with no displayable content
    # (e.g., only ToolCallPart or ThinkingPart)
    return None


class _ConvoHistoryMessage(typing_extensions.TypedDict):
    """Format for messages fetched from a convo history."""
    origin: typing.Literal["user", "llm"]
    text: str
    timestamp: str | None


def _to_convo_history_message(
    message: ai_messages.ModelMessage,
) -> _ConvoHistoryMessage | None:
    for part in message.parts:
        if isinstance(message, ai_messages.ModelRequest):
            if isinstance(part, ai_messages.UserPromptPart):
                assert isinstance(part.content, str)
                return {
                    "origin": "user",
                    "text": part.content,
                    "timestamp": part.timestamp.isoformat(),
                }
        else:
            if isinstance(part, ai_messages.TextPart):
                assert isinstance(part.content, str)
                return {
                    "origin": "llm",
                    "text": part.content,
                    "timestamp": message.timestamp.isoformat(),
                }


def _filter_context_message(
    message: ai_messages.ModelMessage,
) -> ai_messages.ModelMessage | None:
    if isinstance(message, ai_messages.ModelRequest):
        context_parts = [
            part for part in message.parts
            if part.part_kind in REQUEST_CONTEXT_PARTS
        ]
        if len(context_parts) > 0:
            return ai_messages.ModelRequest(
                parts=context_parts,
                instructions=message.instructions,
            )
    elif isinstance(message, ai_messages.ModelResponse):
        context_parts = [
            part for part in message.parts
            if part.part_kind in RESPONSE_CONTEXT_PARTS
        ]
        if len(context_parts) > 0:
            return ai_messages.ModelResponse(
                parts=context_parts,
                model_name=message.model_name,
                timestamp=message.timestamp,
            )
    else:  # pragma: NO COVER
        return None


def _filter_context_messages(
    messages: list[ai_messages.ModelMessage],
) -> list[ai_messages.ModelMessage]:
    return filter(None, [
        _filter_context_message(message) for message in messages
    ])


#==============================================================================
#   In-memory storage for room-based user conversations.
#==============================================================================

@dataclasses.dataclass
class Conversation:
    """Conversation w/ message history for a user / room."""
    name: str
    room_id: str
    message_history: list[ai_messages.ModelMessage]
    uuid: str = dataclasses.field(
        default_factory=uuid.uuid4,
    )

    @property
    async def message_history_dicts(self):
        for message in self.message_history:
            info = _to_convo_history_message(message)
            if info is not None:
                yield info


class NoUserConversations(fastapi.HTTPException):
    def __init__(self, user_name: str):
        self.user_name = user_name
        super().__init__(
            status_code=404,
            detail=f"No conversations for user: {user_name}",
        )


class UnknownConversation(fastapi.HTTPException):
    def __init__(self, user_name: str, convo_uuid: str):
        self.user_name = user_name
        self.convo_uuid = convo_uuid
        super().__init__(
            status_code=404,
            detail=
                f"Unknown conversation UUID: {convo_uuid} for user {user_name}"
        )


class Conversations:

    def __init__(self):
        self._lock = asyncio.Lock()
        # {user_name -> {convo_uuid: Conversation}}
        self._convos = {}

    async def _find_user_conversations(
        self, user_name: str,
    ) -> dict[str, Conversation]:

        user_convos = self._convos.get(user_name)

        if user_convos is None:
            raise NoUserConversations(user_name)

        return user_convos.copy()

    async def _find_conversation(
        self, user_name: str, convo_uuid: str,
    ) -> Conversation:

        user_convos = self._convos.get(user_name)

        if user_convos is None:
            raise NoUserConversations(user_name)

        convo = user_convos.get(convo_uuid)

        if convo is None:
            raise UnknownConversation(user_name, convo_uuid)

        return convo

    async def user_conversations(self, user_name: str) -> dict[str, dict]:
        async with self._lock:
            convos = await self._find_user_conversations(user_name)

            return {
                convo.uuid: {
                    "name": convo.name,
                    "room_id": convo.room_id,
                }
                for convo_uuid, convo in convos.items()
            }

    async def get_conversation(
        self, user_name: str, convo_uuid: str,
    ) -> dict:
        """Return the actual conversation instance

        N.B.:  caller must treat the instance as read-only!
        """
        async with self._lock:
            return await self._find_conversation(user_name, convo_uuid)

    async def get_conversation_info(
        self, user_name: str, convo_uuid: str,
    ) -> dict:
        async with self._lock:
            convo = await self._find_conversation(user_name, convo_uuid)

            messages = []

            async for md in convo.message_history_dicts:
                messages.append(md)

            return {
                "convo_uuid": convo_uuid,
                "name": convo.name,
                "room_id": convo.room_id,
                "message_history": messages,
            }

    async def new_conversation(
        self,
        user_name: str,
        room_id: str,
        convo_name: str,
        new_messages: list[ai_messages.ModelMessage]=(),
    ) -> None:
        """Create a new conversation"""
        convo = Conversation(
            name=convo_name,
            room_id=room_id,
            message_history=list(new_messages),
        )

        messages = []

        async for md in convo.message_history_dicts:
            messages.append(md)

        async with self._lock:
            user_convos = self._convos.setdefault(user_name, {})
            convo_uuid = str(convo.uuid)
            user_convos[convo_uuid] = convo

            return {
                "convo_uuid": convo_uuid,
                "name": convo.name,
                "room_id": convo.room_id,
                "message_history": messages,
            }

    async def append_to_conversation(
        self,
        user_name: str,
        convo_uuid: str,
        new_messages: list[ai_messages.ModelMessage],
    ) -> None:
        """Append messsages to history for a conversation"""
        async with self._lock:
            convo = await self._find_conversation(user_name, convo_uuid)

            convo.message_history.extend(new_messages)

    async def delete_conversation(
        self, user_name: str, convo_uuid: str,
    ) -> None:
        """Remove a conversation"""
        async with self._lock:
            convos = await self._find_user_conversations(user_name)
            try:
                del convos[convo_uuid]
            except KeyError:
                raise UnknownConversation(
                    user_name, convo_uuid
                ) from  None
            self._convos[user_name] = convos


async def get_the_convos(request: fastapi.Request) -> Conversations:
    return request.state.the_convos

depend_the_convos = fastapi.Depends(get_the_convos)
