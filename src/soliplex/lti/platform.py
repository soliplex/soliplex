"""LTI 1.3 platform lookup helpers"""

from __future__ import annotations

import re

from soliplex.config import lti as config_lti

# Room IDs flow into a JSON config block in the rendered HTML and
# are referenced from URLs and JS. Restrict to a safe subset of the
# alphabet to keep them from breaking template substitution or
# leaking into JS as code if a future change ever re-introduces
# direct interpolation. The actual room-ID space in soliplex
# installation configs is already a subset of this character class.
_ROOM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class UnknownLTIPlatform(KeyError):
    def __init__(self, issuer: str, client_id: str):
        self.issuer = issuer
        self.client_id = client_id
        super().__init__(
            f"Unknown LTI platform: issuer={issuer!r}, client_id={client_id!r}"
        )


class InvalidLTIDeployment(ValueError):
    def __init__(
        self,
        deployment_id: str,
        platform_id: str,
    ):
        self.deployment_id = deployment_id
        self.platform_id = platform_id
        super().__init__(
            f"Invalid deployment_id {deployment_id!r}"
            f" for platform {platform_id!r}"
        )


def find_platform(
    platforms: list[config_lti.LTIPlatformConfig],
    *,
    issuer: str,
    client_id: str,
) -> config_lti.LTIPlatformConfig:
    for platform in platforms:
        if platform.issuer == issuer and platform.client_id == client_id:
            return platform
    raise UnknownLTIPlatform(issuer, client_id)


def find_platform_by_id(platforms, platform_id):
    """Look up a platform by its unique ``id`` field."""
    for p in platforms:
        if p.id == platform_id:
            return p
    return None


def check_deployment(
    platform: config_lti.LTIPlatformConfig,
    deployment_id: str,
) -> None:
    if deployment_id not in platform.deployment_ids:
        raise InvalidLTIDeployment(deployment_id, platform.id)


def resolve_room_id(
    platform: config_lti.LTIPlatformConfig,
    *,
    target_link_uri: str | None = None,
    course_id: str | None = None,
) -> str:
    """Resolve target room ID from LTI launch context

    Priority:
      1. Room ID embedded in target_link_uri path: /lti/chat/{room}
      2. course_room_map lookup by Moodle course ID
      3. default_room_id
    """
    if target_link_uri is not None:
        parts = target_link_uri.rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] == "chat":
            candidate = parts[-1]
            if _ROOM_ID_RE.match(candidate):
                return candidate
            # Malformed segment — fall through to course_room_map/default
            # rather than echo attacker-controlled input back into the
            # rendered HTML page.

    if course_id is not None and course_id in platform.course_room_map:
        candidate = platform.course_room_map[course_id]
        if _ROOM_ID_RE.match(candidate):
            return candidate
        # Misconfigured map entry — fall through to default.

    # default_room_id is operator-controlled at config-load time; trust it.
    return platform.default_room_id
