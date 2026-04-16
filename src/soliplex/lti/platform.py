"""LTI 1.3 platform lookup helpers"""

from __future__ import annotations

from soliplex.config import lti as config_lti


class UnknownLTIPlatform(KeyError):
    def __init__(self, issuer: str, client_id: str):
        self.issuer = issuer
        self.client_id = client_id
        super().__init__(
            f"Unknown LTI platform:"
            f" issuer={issuer!r},"
            f" client_id={client_id!r}"
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
        if (
            platform.issuer == issuer
            and platform.client_id == client_id
        ):
            return platform
    raise UnknownLTIPlatform(issuer, client_id)


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
            return parts[-1]

    if (
        course_id is not None
        and course_id in platform.course_room_map
    ):
        return platform.course_room_map[course_id]

    return platform.default_room_id
