"""AI skill for AGUI run feedback

- Allow users to query recent AGUI run feedback
- Allow privileged users to mark feedback a as "reviewed", "resolved".
"""

import datetime
import enum
import typing

import jsonpatch
import pydantic
import pydantic_ai
from ag_ui import core as agui_core

from soliplex import agents
from soliplex import agui
from soliplex.agui import parser as agui_parser

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
#   these are reported to the user via 'RunFeedbackInfo.run_status_note'.
RUN_STATUS_NOTES = {
    agui_parser.RunStatus.INITIALIZED: (
        "The run never started:  nothing was recorded for it."
    ),
    agui_parser.RunStatus.RUNNING: (
        "The run never finished:  it may still be running, or resumable."
    ),
    agui_parser.RunStatus.ERROR: "The run ended with an error.",
    agui_parser.RunStatus.FINISHED: "The run finished normally.",
}


class RunFeedbackInfo(pydantic.BaseModel):
    """Information about the run which was the target of feedback

    Args:

      'user_name' (string):  preferred username of the reporting user.

      'email' (string or None):  email-address of the reporting user.

      'room_id' (string): ID of the room in which the AGUI run originated.

      'thread_id' (string): UUID of the AGUI thread which spawned the run.

      'run_id' (string): UUID of the run against which the feedback was made.

      'user_prompt' (string or None):  the prompt which drove the run, or
        None if the run recorded none.  A run resumed to supply a tool
        result (e.g. a human-in-the-loop approval) has its prompt in an
        earlier run of the same thread.  See 'run_status_note'.

      'agent_response' (string or None):  the agent's reply, or None if the
        run recorded none:  it may have failed, never finished, or answered
        only via tool calls.  See 'run_status_note'.

      'run_status' (one of "INITIALIZED", "RUNNING", "FINISHED", "ERROR"):
        the run's status, recovered by replaying its recorded events.

      'run_status_note' (string):  what that status means for this run.
        Report it to the user when 'user_prompt' or 'agent_response' is
        None:  it explains what became of the run.
    """

    user_name: str
    email: str | None = None
    room_id: str
    thread_id: str
    run_id: str
    user_prompt: str | None = None
    agent_response: str | None = None
    run_status: str
    run_status_note: str


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


async def _do_query(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    query: RecentRunFeedbackQuery,
) -> RecentRunFeedback:
    the_threads = ctx.deps.the_threads
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

    entries = await _do_query(ctx, query)
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
    for attr in from_which_attrs:
        candidates = getattr(our_state.entries, attr)
        for candidate in candidates:
            if candidate.run_id == run_id:
                return candidate, candidates

    raise UnknownFeedback(run_id)


async def get_feedback_run_info(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    run_id: str,
) -> RunFeedbackInfo:
    """Return information about the run against which the feedback was created

    'user_prompt' and / or 'agent_response' come back as None for a run
    which recorded neither;  'run_status_note' explains what became of it,
    and should be reported to the user in that case.

    Args:

      'run_id' is the UUID of the run.
    """
    agui_state = ctx.deps.state
    raw_state = agui_state.get(STATE_NAMESPACE)
    our_state = RecentRunFeedback.model_validate(
        raw_state or {}  # guard against actual 'None'
    )

    to_query, _ = _find_feedback_by_run_id(our_state, run_id)

    the_threads = ctx.deps.the_threads
    run = await the_threads.get_run(
        user_name=to_query.user_name,
        room_id=to_query.room_id,
        thread_id=to_query.thread_id,
        run_id=to_query.run_id,
    )

    thread = await run.awaitable_attrs.thread
    email = await thread.awaitable_attrs.email
    run_input = await run.awaitable_attrs.run_agent_input
    events = await run.awaitable_attrs.events

    esp = agui_parser.EventStreamParser(run_input)

    for event in events:
        try:
            e_model = event.to_agui_model()
        # agui_core.events.Event is not all-inclusive :<
        except pydantic.ValidationError:  # pragma: NO COVER
            continue
        esp(e_model)

    user_prompts = [
        message.content for message in esp.messages if message.role == "user"
    ]

    agent_responses = [
        message.content
        for message in esp.messages
        if message.role == "assistant" and message.content is not None
    ]

    # A degenerate run (never started, died, errored, or answered only via
    # tool calls) may have recorded neither:  report what it did record,
    # explaining the gap via the run's status, rather than failing.
    run_status = esp.run_status

    return RunFeedbackInfo(
        user_name=to_query.user_name,
        email=email,
        room_id=to_query.room_id,
        thread_id=to_query.thread_id,
        run_id=run_id,
        user_prompt=user_prompts[-1] if user_prompts else None,
        agent_response=agent_responses[-1] if agent_responses else None,
        run_status=run_status.name,
        run_status_note=RUN_STATUS_NOTES[run_status],
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

    the_threads = ctx.deps.the_threads
    user = ctx.deps.user
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

    the_threads = ctx.deps.the_threads
    user = ctx.deps.user
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
