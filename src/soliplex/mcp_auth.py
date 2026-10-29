from __future__ import annotations

from fastmcp.server.auth import auth as fmcp_server_auth
from mcp.server.auth import provider as mcp_auth_provider

from soliplex import token_mint

# Backward-compatibility aliases:  remove some time after soliplex v0.91.
generate_url_safe_token = token_mint.generate_url_safe_token
validate_url_safe_token = token_mint.validate_url_safe_token


class FastMCPTokenProvider(fmcp_server_auth.TokenVerifier):
    room_id: str
    max_age: int = None

    def __init__(
        self,
        room_id: str,
        auth_disabled: bool,
        secret_key: str,
        max_age: int = None,
    ):
        self.room_id = room_id
        self.auth_disabled = auth_disabled
        self.secret_key = secret_key
        self.max_age = max_age

        super().__init__()

    async def verify_token(
        self,
        token: str,
    ) -> mcp_auth_provider.AccessToken | None:
        if self.auth_disabled:
            validated = token
        else:
            validated = token_mint.validate_url_safe_token(
                self.secret_key,
                self.room_id,
                token,
                max_age=self.max_age,
            )

        if validated is not None:
            return mcp_auth_provider.AccessToken(
                token=token,
                client_id=self.room_id,
                scopes=(),
            )
