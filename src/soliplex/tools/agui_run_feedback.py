"""AI skill for AGUI run feedback

- Allow users to query recent AGUI run feedback
- Allow privileged users to mark feedback a as "reviewed", "resolved".
"""

import contextlib
import dataclasses
import datetime
import enum
import typing

import jsonpatch
import pydantic
import pydantic_ai
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agents
from soliplex import agui
from soliplex.agui import parser as agui_parser
from soliplex.agui import persistence as agui_persistence

FRS = agui.FeedbackReviewStatus
STATE_NAMESPACE = "soliplex-agui-run-feedback"


class UnknownFeedback(pydantic_ai.ModelRetry):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(
            f"Unknown feedback entry for run id {run_id}. "
            "Call 'query_recent_feedback' and try again."
        )


class RunFeedbackEntry(pydantic.BaseModel):
    """State of the feedback for a give AGUI run

    Args:

      'user_name' (string):  preferred username of reporting user

      'email' (string):  email-address of reporting user

      'room_id' (string): ID of the room in which the AGUI run originated.

      'thread_id' (string): UUID of the AGUI thread which spawned the run.

      'run_id' (string): UUID of the run against which the feedback was made.

      'created' (datetime.datetime): timestamp of the feedback.

      'feedback': (one of "thumbs_up", "thumbs_down") user-supplied feedback.

      'reason' (string or None): user-supplied reason for the feedback.

      'status' (one of None, "reviewed", or "resolved"):  State of the
        feedback in its review / resolution cycle.

      'note': (str, optional): reviewer-supplied description for update
        to the feedback status.
    """

    user_name: str
    email: str | None = None
    room_id: str
    thread_id: str
    run_id: str
    created: datetime.datetime
    feedback: str
    reason: str | None = None
    status: agui.FeedbackReviewStatus | None = None
    note: str | None = None


#   What a run's recovered status means for the info we can show, keyed by
#   the status replaying its events leaves behind.  Phrased to stand alone:
#   these are reported to the user via the 'run_status_note' of
#   'RunFeedbackInfo' and 'TranscriptRun'.
RUN_STATUS_NOTES = {
    agui_parser.RunStatus.INITIALIZED: ("The run never started."),
    agui_parser.RunStatus.RUNNING: (
        "The run never finished:  it may still be running, or resumable."
    ),
    agui_parser.RunStatus.ERROR: "The run ended with an error.",
    agui_parser.RunStatus.FINISHED: "The run finished normally.",
}

#   Appended to the note when replaying the run left state deltas which
#   could not be applied, and which no later snapshot superseded:  the
#   recovered state is missing whatever those deltas carried.
INCOMPLETE_STATE_NOTE = (
    "The state recovered for this run is incomplete:  {count} recorded "
    "state update(s) could not be applied."
)

#   Appended to the note when replaying the run skipped recorded events,
#   either unreadable or rejected by the parser:  what is shown for the run,
#   its status included, is missing whatever those events carried.
SKIPPED_EVENTS_NOTE = (
    "{count} recorded event(s) could not be replayed, so what is shown for "
    "this run, its status included, may be incomplete or wrong."
)


class RunFeedbackInfo(pydantic.BaseModel):
    """Information about the run which was the target of feedback

    Args:

      'user_name' (string):  preferred username of the reporting user.

      'email' (string or None):  email-address of the reporting user.

      'room_id' (string): ID of the room in which the AGUI run originated.

      'thread_id' (string): UUID of the AGUI thread which spawned the run.

      'run_id' (string): UUID of the run against which the feedback was made.

      'parent_run_id' (string or None):  UUID of the run this one continues,
        or None for the first run of its thread.

      'agui_state' (mapping or None):  the AG-UI state as of the end of the
        run, recovered by replaying its recorded events.  It may be
        incomplete;  'run_status_note' says so when it is.

      'user_prompt' (string or None):  the prompt which drove the run, or
        None if the run recorded none.  A run resumed to supply a tool
        result (e.g. a human-in-the-loop approval) has its prompt in an
        earlier run of the same thread.  See 'run_status_note'.

      'agent_response' (string or None):  the agent's reply, or None if the
        run recorded none:  it may have failed, never finished, or answered
        only via tool calls.  See 'run_status_note'.

      'run_status' (one of "INITIALIZED", "RUNNING", "FINISHED", "ERROR"):
        the run's status, recovered by replaying its recorded events.

      'run_status_note' (string):  what that status means for this run, and
        whether what was recovered for it is incomplete.  Report it to the
        user unless it is just "The run finished normally.":  it explains
        what became of the run.
    """

    user_name: str
    email: str | None = None
    room_id: str
    thread_id: str
    run_id: str
    parent_run_id: str | None = None
    agui_state: dict[str, typing.Any] | None = None
    user_prompt: str | None = None
    agent_response: str | None = None
    run_status: str
    run_status_note: str


#   Tool results longer than this are cut short in a thread transcript.
TOOL_RESULT_LIMIT = 2000

#   Message roles which appear in a thread transcript.
TRANSCRIPT_ROLES = ("user", "assistant", "tool")


class TranscriptToolCall(pydantic.BaseModel):
    """A tool call made by the agent

    Args:

      'tool_call_id' (string):  ID of the call;  a 'tool' message with the
        same 'tool_call_id' holds its result.

      'name' (string):  name of the tool called.

      'arguments' (string):  JSON-encoded arguments passed to the tool.
    """

    tool_call_id: str
    name: str
    arguments: str


class TranscriptMessage(pydantic.BaseModel):
    """One message in a thread transcript

    Args:

      'message_id' (string):  ID of the message.

      'role' (one of "user", "assistant", "tool"):  "user" messages are
        the user's prompts, "assistant" messages are the agent's replies
        and tool calls, "tool" messages are tool results (including the
        user's answers to human-in-the-loop tool calls), present only when
        requested.

      'content' (string or None):  text of the message.  Non-text parts
        of a user message appear as '[<type>]' placeholders.  Tool results
        are cut short after 'TOOL_RESULT_LIMIT' characters.

      'tool_calls' (list):  tool calls made in an "assistant" message.

      'tool_call_id' (string or None):  for a "tool" message, the ID of the
        call whose result it holds.

      'error' (string or None):  for a "tool" message, the error raised by
        the tool, if any.
    """

    message_id: str
    role: str
    content: str | None = None
    tool_calls: list[TranscriptToolCall] = []
    tool_call_id: str | None = None
    error: str | None = None


class TranscriptRun(pydantic.BaseModel):
    """One run in a thread transcript

    Args:

      'run_id' (string):  UUID of the run.

      'parent_run_id' (string or None):  UUID of the run this one
        continues, or None.

      'created' (datetime.datetime):  when the run was created.

      'run_status' (one of "INITIALIZED", "RUNNING", "FINISHED", "ERROR"):
        the run's status, recovered by replaying its recorded events.

      'run_status_note' (string):  what that status means for this run,
        and whether what was recovered for it is incomplete.

      'feedback' (one of None, "thumbs_up", "thumbs_down"):  feedback
        given by the user for this run, if any.

      'feedback_reason' (string or None):  reason given with the
        feedback.

      'messages' (list):  messages which first appear in this run, in
        order.  Earlier messages of the thread are in earlier runs.
    """

    run_id: str
    parent_run_id: str | None = None
    created: datetime.datetime
    run_status: str
    run_status_note: str
    feedback: str | None = None
    feedback_reason: str | None = None
    messages: list[TranscriptMessage] = []


class ThreadTranscript(pydantic.BaseModel):
    """Everything recorded for the thread of a feedback entry

    Args:

      'user_name' (string):  preferred username of the thread's user.

      'email' (string or None):  email-address of the thread's user.

      'room_id' (string): ID of the room in which the thread was created.

      'thread_id' (string): UUID of the thread.

      'runs' (list):  the thread's runs, oldest first.

      'agui_state' (mapping or None):  the AG-UI state recovered from the
        thread's last run with recorded input, if requested;  None if no
        run recorded input.

      'agui_state_run_id' (string or None):  UUID of the run 'agui_state'
        came from;  its 'run_status_note' says whether it is incomplete.
    """

    user_name: str
    email: str | None = None
    room_id: str
    thread_id: str
    runs: list[TranscriptRun] = []
    agui_state: dict[str, typing.Any] | None = None
    agui_state_run_id: str | None = None


class RecentRunFeedbackQuery(pydantic.BaseModel):
    """Define a query for recent AGUI run feedback

    Args:

      'user_name' (string, default None):  user name of reporting user
        If passed, include feedback only from the user whose username
        matches this value.

      'email' (string, default None):  email of reporting user
        If passed, include feedback only from the user whose email
        matches this value.

      'room_id' (string, default None): ID of the room in which the
        AGUI run originated.  If passed, include feedback only for runs
        in this rooom.

      'limit' (integer, default None): the maximun number of feedback
        entries to return.  If neither 'limit' nor 'since' are passed,
        apply a system-defined limit.

      'since' (datetime, default None): if passed, only include feedback
        reported later than this value.
    """

    user_name: str | None = None
    email: str | None = None
    room_id: str | None = None
    limit: int | None = None
    since: datetime.datetime | None = None

    @property
    def as_kwargs(self) -> dict[str, typing.Any]:
        candidates = {
            "user_name": self.user_name,
            "email": self.email,
            "room_id": self.room_id,
            "limit": self.limit,
            "since": self.since,
        }
        return {
            key: value
            for key, value in candidates.items()
            if value is not None
        }


class RecentRunFeedbackEntries(pydantic.BaseModel):
    """Recent feedback, divided into three buckets:

    - 'opened' entries have not yet been reviewed or resolved.

    - 'reviewed' entries have been reviewed, but not yet resolved.

    - 'resolved' entries have been resolved.
    """

    opened: list[RunFeedbackEntry] = []
    reviewed: list[RunFeedbackEntry] = []
    resolved: list[RunFeedbackEntry] = []


class RecentRunFeedback(pydantic.BaseModel):
    query: RecentRunFeedbackQuery | None = None
    entries: RecentRunFeedbackEntries | None = None


class FeedbackReview(pydantic.BaseModel):
    """Record a user's review for a feedback entry

    Args:

      'run_id' (string):  the UUID of the feedback entry's run.

      'note' (string): User-suppled note for the review
    """

    run_id: str
    note: str | None = None


class FeedbackResolution(pydantic.BaseModel):
    """Record a user's resolution of a feedback entry

    Args:

      'run_id' (string):  the UUID of the feedback entry's run.

      'note' (string): User-suppled note for the resolution.
    """

    run_id: str
    note: str | None = None


@contextlib.asynccontextmanager
async def _get_threads_storage(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
):
    """Context manager for tool-call local thread storage / session

    Cannot be derived from the FastAPI request dependency, because
    tool calls must run / complete in their own boundaries.
    """
    engine = ctx.deps.thread_persistence_engine
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        # One transaction per tool call: the storage methods no longer
        # commit, so the tool call owns the unit of work -- committed on a
        # clean response, rolled back if the handler raises.
        async with session.begin():
            yield agui_persistence.ThreadStorage(session)


async def _do_query(
    the_threads: agui_persistence.ThreadStorage,
    query: RecentRunFeedbackQuery,
) -> RecentRunFeedback:
    runs_w_recent_fb = await the_threads.list_recent_run_feedback(
        **query.as_kwargs,
    )

    entries = RecentRunFeedbackEntries()

    for run in runs_w_recent_fb:
        thread = await run.awaitable_attrs.thread
        run_feedback = await run.awaitable_attrs.run_feedback
        history = await run_feedback.awaitable_attrs.review_history
        status_notes = [
            (
                await entry.awaitable_attrs.status,
                await entry.awaitable_attrs.note,
            )
            for entry in history
        ]

        if len(status_notes) > 0:
            status, note = status_notes[0]
        else:
            status = note = None

        entry = RunFeedbackEntry(
            user_name=await thread.awaitable_attrs.user_name,
            email=await thread.awaitable_attrs.email,
            room_id=await thread.awaitable_attrs.room_id,
            thread_id=await thread.awaitable_attrs.thread_id,
            run_id=await run.awaitable_attrs.run_id,
            feedback=await run_feedback.awaitable_attrs.feedback,
            reason=await run_feedback.awaitable_attrs.reason,
            created=await run_feedback.awaitable_attrs.created,
            status=status,
            note=note,
        )

        if status == FRS.RESOLVED:
            entries.resolved.insert(0, entry)

        elif status == FRS.REVIEWED:
            entries.reviewed.insert(0, entry)

        else:
            # Paranoid defence against a "can't get here" condition
            assert entry.status is None
            entries.opened.insert(0, entry)

    return entries


def _response_metadata(before, after) -> list[agui_core.Event]:
    patch = jsonpatch.make_patch(before, after)
    delta = patch.patch

    if not delta:
        return []
    else:
        return [agui_core.StateDeltaEvent(delta=patch.patch)]


async def query_recent_feedback(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    query: RecentRunFeedbackQuery,
) -> pydantic_ai.ToolReturn:
    """Query recent feedback for AGUI runs

    The returned results will be in three buckets:

    - `resolved` will contain feedback entries which have been resolved.

    - `reviewed` will contain feedback etnries which have been reviewed,
      but not yet resolved.

    - `opened` will contain feedback entries which have not yet
      been reviewed or resolved.
    """
    agui_state = ctx.deps.state
    raw_state = agui_state.get(STATE_NAMESPACE)
    our_state = RecentRunFeedback.model_validate(
        raw_state or {}  # guard against actual 'None'
    )
    before_state = {} if raw_state is None else {STATE_NAMESPACE: raw_state}

    async with _get_threads_storage(ctx) as the_threads:
        entries = await _do_query(the_threads, query)
    our_state.query = query
    our_state.entries = entries

    after_json = our_state.model_dump(mode="json")
    after_state = {STATE_NAMESPACE: after_json}
    metadata = _response_metadata(before_state, after_state)

    agui_state[STATE_NAMESPACE] = after_json

    return pydantic_ai.ToolReturn(our_state.entries, metadata=metadata)


class FromWhichAttrs(enum.StrEnum):
    OPENED = "opened"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"


_ALL_FROM_WHICH_ATTRS = tuple(FromWhichAttrs)


def _find_feedback_by_run_id(
    our_state: RecentRunFeedback,
    run_id: str,
    from_which_attrs: typing.Sequence[FromWhichAttrs] = _ALL_FROM_WHICH_ATTRS,
) -> tuple[RunFeedbackEntry, list[RunFeedbackEntry]]:
    """Find a feedback entry based on its run ID

    Search state's entries using the given attribute names
    """
    if our_state.entries is None:
        # No 'query_recent_feedback' yet in this thread:  ask the model to
        # call it, rather than failing on the missing entries.
        raise UnknownFeedback(run_id)

    for attr in from_which_attrs:
        candidates = getattr(our_state.entries, attr)
        for candidate in candidates:
            if candidate.run_id == run_id:
                return candidate, candidates

    raise UnknownFeedback(run_id)


@dataclasses.dataclass
class _ReplayedRun:
    """A run replayed in its thread, with the messages first appearing in it"""

    run: agui.Run
    run_id: str
    esp: agui_parser.EventStreamParser
    skipped_events: int
    new_messages: list

    @property
    def run_status_note(self) -> str:
        notes = [RUN_STATUS_NOTES[self.esp.run_status]]

        if self.esp.invalid_state_deltas:
            notes.append(
                INCOMPLETE_STATE_NOTE.format(
                    count=len(self.esp.invalid_state_deltas),
                )
            )

        if self.skipped_events:
            notes.append(SKIPPED_EVENTS_NOTE.format(count=self.skipped_events))

        return "  ".join(notes)


async def _replay_thread(
    thread: agui.Thread,
) -> typing.AsyncIterator[_ReplayedRun]:
    """Replay each of a thread's runs, oldest first

    A run's input normally repeats the messages before it:  a run's
    'new_messages' are those which no earlier run held.
    """
    seen_message_ids = set()

    for run in await thread.awaitable_attrs.runs:
        run_input = await run.awaitable_attrs.run_agent_input
        esp = agui_parser.EventStreamParser(run_input)
        skipped_events = 0

        for event in await run.awaitable_attrs.events:
            # The parser raises 'EPSError' before changing anything, so
            # replay can go on past a rejected event, as it does past an
            # unreadable one.
            try:
                esp(event.to_agui_model())
            except (pydantic.ValidationError, agui_parser.EPSError):
                skipped_events += 1

        new_messages = [
            message
            for message in esp.messages
            if message.id not in seen_message_ids
        ]
        seen_message_ids.update(message.id for message in new_messages)

        yield _ReplayedRun(
            run=run,
            run_id=await run.awaitable_attrs.run_id,
            esp=esp,
            skipped_events=skipped_events,
            new_messages=new_messages,
        )


async def _get_entry_thread(the_threads, to_query: RunFeedbackEntry):
    try:
        return await the_threads.get_thread(
            user_name=to_query.user_name,
            room_id=to_query.room_id,
            thread_id=to_query.thread_id,
        )
    except agui.UnknownThread:
        # The entry's thread no longer exists.
        raise UnknownFeedback(to_query.run_id) from None


def _content_text(content) -> str | None:
    """Render message content as text, with placeholders for non-text parts"""
    if content is None or isinstance(content, str):
        return content

    return "\n".join(
        part.text if part.type == "text" else f"[{part.type}]"
        for part in content
    )


def _transcript_message(message) -> TranscriptMessage:
    content = _content_text(message.content)

    if message.role == "tool" and len(content) > TOOL_RESULT_LIMIT:
        omitted = len(content) - TOOL_RESULT_LIMIT
        content = (
            f"{content[:TOOL_RESULT_LIMIT]}... [{omitted} characters omitted]"
        )

    tool_calls = [
        TranscriptToolCall(
            tool_call_id=tool_call.id,
            name=tool_call.function.name,
            arguments=tool_call.function.arguments,
        )
        for tool_call in getattr(message, "tool_calls", None) or ()
    ]

    return TranscriptMessage(
        message_id=message.id,
        role=message.role,
        content=content,
        tool_calls=tool_calls,
        tool_call_id=getattr(message, "tool_call_id", None),
        error=getattr(message, "error", None),
    )


async def get_feedback_run_info(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    run_id: str,
) -> RunFeedbackInfo:
    """Return information about the run against which the feedback was created

    'user_prompt' is the run's own last prompt, and 'agent_response' its
    last reply;  either is None if the run recorded none of its own.  E.g.
    a run resumed to supply a tool result (a human-in-the-loop approval)
    has no prompt of its own:  'get_feedback_thread_transcript' shows the
    earlier run holding it.  Report 'run_status_note' to the user unless
    it is just "The run finished normally.".

    Args:

      'run_id' is the UUID of the run.
    """
    agui_state = ctx.deps.state
    raw_state = agui_state.get(STATE_NAMESPACE)
    our_state = RecentRunFeedback.model_validate(
        raw_state or {}  # guard against actual 'None'
    )

    to_query, _ = _find_feedback_by_run_id(our_state, run_id)

    async with _get_threads_storage(ctx) as the_threads:
        thread = await _get_entry_thread(the_threads, to_query)
        email = await thread.awaitable_attrs.email

        async with contextlib.aclosing(_replay_thread(thread)) as replayed:
            async for replayed_run in replayed:
                if replayed_run.run_id == to_query.run_id:
                    break
            else:
                raise UnknownFeedback(run_id)

        parent_run_id = await replayed_run.run.awaitable_attrs.parent_run_id

    user_prompts = [
        _content_text(message.content)
        for message in replayed_run.new_messages
        if message.role == "user"
    ]

    agent_responses = [
        message.content
        for message in replayed_run.new_messages
        if message.role == "assistant" and message.content is not None
    ]

    # A degenerate run (never started, died, errored, resumed without a
    # prompt, or answered only via tool calls) may lack a prompt, a reply,
    # or both:  report what it did record, explaining the gap via the run's
    # status note, rather than failing.
    return RunFeedbackInfo(
        user_name=to_query.user_name,
        email=email,
        room_id=to_query.room_id,
        thread_id=to_query.thread_id,
        run_id=run_id,
        parent_run_id=parent_run_id,
        agui_state=replayed_run.esp.state,
        user_prompt=user_prompts[-1] if user_prompts else None,
        agent_response=agent_responses[-1] if agent_responses else None,
        run_status=replayed_run.esp.run_status.name,
        run_status_note=replayed_run.run_status_note,
    )


async def get_feedback_thread_transcript(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    run_id: str,
    include_tool_results: bool = False,
    include_agui_state: bool = False,
) -> ThreadTranscript:
    """Return the transcript of the thread containing a feedback entry's run

    The transcript lists every run of the thread, oldest first.  Each run
    holds the messages which first appear in it:  the user's prompts, the
    agent's replies and tool calls, and (if requested) the tool results.
    Runs which received feedback carry it in 'feedback' and
    'feedback_reason'.  Each run's 'run_status_note' explains its
    'run_status':  report it unless it is just "The run finished
    normally.".
    System, developer, reasoning, and activity messages are left out.

    Args:

      'run_id' is the UUID of the feedback entry's run.

      'include_tool_results' (default False):  if True, include "tool"
        messages holding tool results.  They can be large:  request them
        only when the user asks what a tool returned.  Long results are
        cut short, ending with '... [<n> characters omitted]'.

      'include_agui_state' (default False):  if True, include the AG-UI
        state recovered from the thread's last run with recorded input
        (None if no run recorded any), and that run's ID in
        'agui_state_run_id'.  It can be very large:
        request it only when the user asks about the state.
        'get_feedback_run_info' returns the state as of the end of the
        feedback entry's own run.
    """
    agui_state = ctx.deps.state
    raw_state = agui_state.get(STATE_NAMESPACE)
    our_state = RecentRunFeedback.model_validate(
        raw_state or {}  # guard against actual 'None'
    )

    to_query, _ = _find_feedback_by_run_id(our_state, run_id)

    if include_tool_results:
        roles = TRANSCRIPT_ROLES
    else:
        roles = tuple(role for role in TRANSCRIPT_ROLES if role != "tool")

    transcript_runs = []
    last_state = last_state_run_id = None

    async with _get_threads_storage(ctx) as the_threads:
        thread = await _get_entry_thread(the_threads, to_query)
        email = await thread.awaitable_attrs.email

        async for replayed in _replay_thread(thread):
            # A run with no recorded input replays from empty state, not
            # from the thread's.
            if replayed.esp.run_input is not None:
                last_state = replayed.esp.state
                last_state_run_id = replayed.run_id

            run_feedback = await replayed.run.awaitable_attrs.run_feedback

            if run_feedback is not None:
                feedback = await run_feedback.awaitable_attrs.feedback
                feedback_reason = await run_feedback.awaitable_attrs.reason
            else:
                feedback = feedback_reason = None

            transcript_runs.append(
                TranscriptRun(
                    run_id=replayed.run_id,
                    parent_run_id=(
                        await replayed.run.awaitable_attrs.parent_run_id
                    ),
                    created=await replayed.run.awaitable_attrs.created,
                    run_status=replayed.esp.run_status.name,
                    run_status_note=replayed.run_status_note,
                    feedback=feedback,
                    feedback_reason=feedback_reason,
                    messages=[
                        _transcript_message(message)
                        for message in replayed.new_messages
                        if message.role in roles
                    ],
                )
            )

    return ThreadTranscript(
        user_name=to_query.user_name,
        email=email,
        room_id=to_query.room_id,
        thread_id=to_query.thread_id,
        runs=transcript_runs,
        agui_state=last_state if include_agui_state else None,
        agui_state_run_id=last_state_run_id if include_agui_state else None,
    )


async def review_recent_feedback(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    review: FeedbackReview,
) -> pydantic_ai.ToolReturn:
    """Add a user's review to a feedback entry for an AGUI run."""
    agui_state = ctx.deps.state
    raw_state = agui_state.get(STATE_NAMESPACE)
    our_state = RecentRunFeedback.model_validate(
        raw_state or {}  # guard against actual 'None'
    )
    before_state = {} if raw_state is None else {STATE_NAMESPACE: raw_state}

    to_review, _ = _find_feedback_by_run_id(
        our_state, review.run_id, [FromWhichAttrs.OPENED]
    )

    user = ctx.deps.user
    async with _get_threads_storage(ctx) as the_threads:
        await the_threads.review_run_feedback(
            reviewer_user_name=user.preferred_username,
            reviewer_email=user.email,
            note=review.note,
            user_name=to_review.user_name,
            room_id=to_review.room_id,
            thread_id=to_review.thread_id,
            run_id=to_review.run_id,
        )

    to_review.status = FRS.REVIEWED
    to_review.note = review.note
    our_state.entries.opened.remove(to_review)
    our_state.entries.reviewed.insert(0, to_review)

    after_json = our_state.model_dump(mode="json")
    after_state = {STATE_NAMESPACE: after_json}
    metadata = _response_metadata(before_state, after_state)

    agui_state[STATE_NAMESPACE] = after_json

    return pydantic_ai.ToolReturn(our_state.entries, metadata=metadata)


async def resolve_recent_feedback(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    resolution: FeedbackResolution,
) -> pydantic_ai.ToolReturn:
    """Add a user's resolution of a feedback entry for an AGUI run."""
    agui_state = ctx.deps.state
    raw_state = agui_state.get(STATE_NAMESPACE)
    our_state = RecentRunFeedback.model_validate(
        raw_state or {}  # guard against actual 'None'
    )
    before_state = {} if raw_state is None else {STATE_NAMESPACE: raw_state}

    to_resolve, from_which = _find_feedback_by_run_id(
        our_state,
        resolution.run_id,
        [FromWhichAttrs.OPENED, FromWhichAttrs.REVIEWED],
    )

    user = ctx.deps.user
    async with _get_threads_storage(ctx) as the_threads:
        await the_threads.resolve_run_feedback(
            resolver_user_name=user.preferred_username,
            resolver_email=user.email,
            note=resolution.note,
            user_name=to_resolve.user_name,
            room_id=to_resolve.room_id,
            thread_id=to_resolve.thread_id,
            run_id=to_resolve.run_id,
        )

    to_resolve.status = FRS.RESOLVED
    to_resolve.note = resolution.note
    from_which.remove(to_resolve)
    our_state.entries.resolved.insert(0, to_resolve)

    after_json = our_state.model_dump(mode="json")
    after_state = {STATE_NAMESPACE: after_json}
    metadata = _response_metadata(before_state, after_state)

    agui_state[STATE_NAMESPACE] = after_json

    return pydantic_ai.ToolReturn(our_state.entries, metadata=metadata)
