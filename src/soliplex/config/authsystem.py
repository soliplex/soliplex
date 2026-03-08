from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import ssl
import typing

from . import _utils
from . import exceptions as config_exc

_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_default_list_field = _utils._default_list_field


# ============================================================================
#   OIDC Authentication system configuration types
# ============================================================================

WELL_KNOWN_OPENID_CONFIGURATION = ".well-known/openid-configuration"


@dataclasses.dataclass(kw_only=True)
class OIDCAuthSystemConfig:
    id: str
    title: str

    server_url: str
    token_validation_pem: str
    client_id: str
    scope: str = None
    client_secret: str = ""  # "env:{JOSCE_CLIENT_SECRET}"
    oidc_client_pem_path: pathlib.Path = None

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycles
        config_path: pathlib.Path,
        config_dict: dict[str, typing.Any],
    ):
        config_dict["_installation_config"] = installation_config
        config_dict["_config_path"] = config_path

        oidc_client_pem_path = config_dict.pop("oidc_client_pem_path", None)
        if oidc_client_pem_path is not None:
            config_dict["oidc_client_pem_path"] = (
                config_path.parent / oidc_client_pem_path
            )

        try:
            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "oidc",
                config_dict,
            ) from exc

    @property
    def server_metadata_url(self):
        return f"{self.server_url}/{WELL_KNOWN_OPENID_CONFIGURATION}"

    @property
    def oauth_client_kwargs(self) -> dict:
        client_kwargs = {}

        if self.scope is not None:
            client_kwargs["scope"] = self.scope

        if self.oidc_client_pem_path is not None:
            client_kwargs["verify"] = ssl.create_default_context(
                cafile=self.oidc_client_pem_path
            )

        try:
            client_secret = self._installation_config.get_secret(
                self.client_secret
            )
        except Exception:
            client_secret = self.client_secret

        return {
            "name": self.id,
            "server_metadata_url": self.server_metadata_url,
            "client_id": self.client_id,
            "client_secret": client_secret,
            "client_kwargs": client_kwargs,
            # added by the auth setup
            # "authorize_state": main.SESSION_SECRET_KEY,
        }


@dataclasses.dataclass(kw_only=True)
class AvailableOIDCAuthSystemConfigs:
    systems: list[OIDCAuthSystemConfig] = _default_list_field()
