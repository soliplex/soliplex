"""LTI 1.3 platform registration configuration"""

from __future__ import annotations

import dataclasses
import pathlib
import typing

from . import _utils
from . import exceptions as config_exc

_default_list_field = _utils._default_list_field
_default_dict_field = _utils._default_dict_field
_no_repr_no_compare_none = _utils._no_repr_no_compare_none


@dataclasses.dataclass(kw_only=True)
class LTIPlatformConfig:
    """Configuration for a single LTI 1.3 platform (e.g. Moodle)"""

    id: str
    issuer: str
    client_id: str
    deployment_ids: list[str] = _default_list_field()
    auth_login_url: str
    # Platform's OAuth2 token endpoint, used for LTI back-channel
    # service calls (AGS, NRPS, etc.). Soliplex does not yet make
    # those calls, so the field is read at config load but not used
    # at runtime. Optional; populate when adding back-channel features.
    auth_token_url: str = ""
    key_set_url: str
    default_room_id: str
    course_room_map: dict[str, str] = _default_dict_field()
    show_room_picker: bool = False
    session_ttl: int = 3600

    _config_path: pathlib.Path = _no_repr_no_compare_none()

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: dict[str, typing.Any],
    ):
        try:
            config_dict = dict(config_dict)
            config_dict["_config_path"] = config_path
            instance = cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "lti_platform",
                config_dict,
            ) from exc

        # Defended at config load rather than at launch time: an empty
        # deployment_ids list silently rejects every LTI launch and is
        # almost always a misconfiguration the operator wants to know
        # about immediately.
        if not instance.deployment_ids:
            raise config_exc.FromYamlException(
                config_path,
                "lti_platform",
                config_dict,
            ) from ValueError("deployment_ids must contain at least one entry")

        return instance
