"""AI skill for AGUI run feedback

- Allow users to query recent AGUI run feedback
- Allow privileged users to mark feedback a as "reviewd", "resolved".
"""

import datetime
import pathlib

import pydantic
import pydantic_ai
from haiku.skills import models as hs_models
from haiku.skills import parser as hs_parser
from haiku.skills import state as hs_state

from soliplex import agui as agui_package

STATE_NAMESPACE = "soliplex-agui-run-feedback"


class NoThreadsStorage(ValueError):
    def __init__(self, ctx: pydantic_ai.RunContext):
        self.ctx = ctx
        msg = f"No 'the_threads' in context [{','.join(dir(ctx))}]"
        super().__init__(msg)


class StateTypeMismatch(ValueError):
    def __init__(self, state):
        self.state = state
        super().__init__(
            f"Skill state mismatch:  expected 'RecentRunFeedback', "
            f"got '{type(state).__name__}'."
        )


class RunFeedbackEntry(pydantic.BaseModel):
    """State of the feedback for a give AGUI run

    Args:

      'user_name' (string):  email-address of reporting user

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
    room_id: str
    thread_id: str
    run_id: str
    created: datetime.datetime
    feedback: str
    reason: str | None
    status: agui_package.FeedbackReviewStatus | None
    note: str | None


class RecentRunFeedbackQuery(pydantic.BaseModel):
    """Define a query for recent AGUI run feedback

    Args:

      'user_name' (string, default None):  email-address of reporting user
        If passed, include feedback only from the user whose username
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
    room_id: str | None = None
    limit: int | None = None
    since: datetime.datetime | None = None


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


async def _do_query(
    ctx: pydantic_ai.RunContext[hs_state.SkillRunDeps],
    query: RecentRunFeedbackQuery,
) -> RecentRunFeedback:
    deps = getattr(ctx, "deps", None)
    the_threads = getattr(deps, "the_threads", None)

    if the_threads is None:
        raise NoThreadsStorage(ctx)

    recent = await the_threads.list_recent_run_feedback(
        user_name=query.user_name,
        room_id=query.room_id,
        limit=query.limit,
        since=query.since,
    )

    entries = RecentRunFeedbackEntries()

    for run_feedback in recent:
        run = await run_feedback.awaitable_attrs.run
        review_history = await run_feedback.awaitable_attrs.review_history
        last = review_history[0]
        entry = RunFeedbackEntry(
            user_name=await run.awaitable_attrs.user_name,
            room_id=await run.awaitable_attrs.room_id,
            thread_id=await run.awaitable_attrs.thread_id,
            run_id=await run.awaitable_attrs.run_id,
            feedback=await run_feedback.awaitable_attrs.feedback,
            reason=await run_feedback.awaitable_attrs.reason,
            created=await run_feedback.awaitable_attrs.created,
            status=await last.awaitable_attrs.status,
            note=await last.awaitable_attrs.note,
        )

        if entry.status == "resolved":
            entries.resolved.insert(0, entry)

        elif entry.status == "reviewed":
            entries.reviewed.insert(0, entry)

        else:
            entries.opened.insert(0, entry)

    return entries


async def query_recent_feedback(
    ctx: pydantic_ai.RunContext[hs_state.SkillRunDeps],
    query: RecentRunFeedbackQuery,
) -> RecentRunFeedback:
    """Query recent feedback for AGUI runs

    Store the query and retrieved entries in the AGUI state for this skill.
    """
    deps = getattr(ctx, "deps", None)
    state = getattr(deps, "state", None)
    if state is not None and isinstance(state, RecentRunFeedback):
        if query != state.query:
            entries = await _do_query(ctx, query)
            ctx.state = RecentRunFeedback(
                query=query,
                entries=entries,
            )
    return ctx.state.entries


def create_skill() -> hs_models.Skill:
    skill_dir = pathlib.Path(__file__).parent / "agui-run-feedback"
    metadata, instructions = hs_parser.parse_skill_md(skill_dir / "SKILL.md")

    return hs_models.Skill(
        metadata=metadata,
        source=hs_models.SkillSource.ENTRYPOINT,
        path=skill_dir,
        instructions=instructions,
        tools=[
            query_recent_feedback,
        ],
        state_type=RecentRunFeedback,
        state_namespace=STATE_NAMESPACE,
    )
