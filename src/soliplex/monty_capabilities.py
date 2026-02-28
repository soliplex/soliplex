"""Gate monty skills based on client bridge version.

The Flutter client sends an ``X-Monty-Version`` header declaring which
bridge version it supports.  The backend uses this to include or exclude
auto-generated monty skills from the agent context.

When the header is absent or the declared version is lower than the
expected version, all skills whose ``metadata["generated"]`` is
``"true"`` are excluded.  Non-monty skills always pass through.
"""

from __future__ import annotations

EXPECTED_BRIDGE_VERSION = 1

HEADER_NAME = "X-Monty-Version"


def parse_monty_version(header_value: str | None) -> int | None:
    """Parse the ``X-Monty-Version`` header value.

    Returns ``None`` when the header is absent, empty, or not a valid
    integer — the caller should treat ``None`` as "client has no monty
    support".
    """
    if not header_value:
        return None
    try:
        return int(header_value.strip())
    except ValueError:
        return None


def filter_skill_configs(
    skill_configs: dict,
    client_version: int | None,
) -> dict:
    """Return skills the client is allowed to see.

    If *client_version* is ``None`` or less than
    ``EXPECTED_BRIDGE_VERSION``, all auto-generated monty skills are
    stripped.  Every other skill passes through unchanged.
    """
    if (
        client_version is not None
        and client_version >= EXPECTED_BRIDGE_VERSION
    ):
        return skill_configs

    return {
        name: skill
        for name, skill in skill_configs.items()
        if (skill.metadata or {}).get("generated") != "true"
    }
