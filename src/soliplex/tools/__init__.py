import datetime

import pydantic_ai

from soliplex import agents
from soliplex import agui
from soliplex import models


async def get_current_datetime() -> str:
    """
    Get the current date and time in ISO format.

    Returns:
        str: Current datetime in ISO format with timezone information.
    """
    return datetime.datetime.now(datetime.UTC).isoformat()


async def get_current_user(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> models.UserProfile:
    """Return information from the current user's profile."""
    return ctx.deps.user


async def agui_state(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> agui.AGUI_State:
    """Return the AGUI state."""
    return ctx.deps.state
