from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import pathlib
import ssl
import typing

from . import _utils
from . import exceptions as config_exc
from . import interpolation as config_interp

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from . import installation as config_installation

_default_list_field = _utils._default_list_field
_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_secret_whole_or_literal_field = config_interp.secret_whole_or_literal_field


# ============================================================================
#   OIDC Authentication system configuration types
# ============================================================================

WELL_KNOWN_OPENID_CONFIGURATION = ".well-known/openid-configuration"


class UnlistedFrontendOriginPolicy(enum.StrEnum):
    CONSENT_REQUIRED = "consent-required"
    DENY_ALL = "deny-all"


@dataclasses.dataclass(kw_only=True)
class OIDCAuthSystemConfig:
    id: str
    title: str

    server_url: str
    token_validation_pem: str
    client_id: str
    scope: str = None
    # A 'secret:' reference is resolved; any other value is used as a
    # literal.  'env:' markers are not honored here.
    client_secret: str = _secret_whole_or_literal_field(default="")
    oidc_client_pem_path: pathlib.Path = None
    consent_template_path: pathlib.Path = None

    allowed_frontend_origins: list[str] = _default_list_field()
    unlisted_frontend_origin: UnlistedFrontendOriginPolicy = (
        UnlistedFrontendOriginPolicy.CONSENT_REQUIRED
    )

    # Set in 'from_yaml' below
    _installation_config: config_installation.InstallationConfig = (
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
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

        consent_template_path = config_dict.pop("consent_template_path", None)
        if consent_template_path is not None:
            config_dict["consent_template_path"] = (
                config_path.parent / consent_template_path
            )

        ufo = config_dict.pop("unlisted_frontend_origin", None)
        if ufo is not None:
            config_dict["unlisted_frontend_origin"] = (
                UnlistedFrontendOriginPolicy(ufo)
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
    def as_yaml(self) -> dict:
        result = {
            "id": self.id,
            "title": self.title,
            "server_url": self.server_url,
            "token_validation_pem": self.token_validation_pem,
            "client_id": self.client_id,
        }

        if self.scope is not None:
            result["scope"] = self.scope

        if self.client_secret:
            # Dumped raw: 'env:'/'secret:' interpolations are not resolved.
            result["client_secret"] = self.client_secret

        if self.oidc_client_pem_path is not None:
            # Absolutized against the config dir on load.  See #1228.
            result["oidc_client_pem_path"] = str(self.oidc_client_pem_path)

        if self.consent_template_path is not None:
            # Absolutized against the config dir on load.  See #1228.
            result["consent_template_path"] = str(self.consent_template_path)

        if self.allowed_frontend_origins:
            result["allowed_frontend_origins"] = self.allowed_frontend_origins

        if (
            self.unlisted_frontend_origin
            is not UnlistedFrontendOriginPolicy.CONSENT_REQUIRED
        ):
            result["unlisted_frontend_origin"] = self.unlisted_frontend_origin

        return result

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

        client_secret = config_interp.resolve_field(self, "client_secret")

        return {
            "name": self.id,
            "server_metadata_url": self.server_metadata_url,
            "client_id": self.client_id,
            "client_secret": client_secret,
            "client_kwargs": client_kwargs,
            # added by the auth setup
            # "authorize_state": main.SESSION_SECRET_KEY,
        }
