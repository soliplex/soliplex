from __future__ import annotations  # forward refs

from fastmcp.server.auth import auth as fmcp_server_auth
from itsdangerous import url_safe as id_url_safe
from mcp.server.auth import provider as mcp_auth_provider

from soliplex import installation


def generate_url_safe_token(secret_key: str, salt: str, **kw) -> str:
    """Generate a signed token for a given context

    'secret_key':
        Key use for symmetric encryption of the token.

    'salt':
        the "context" for the token (e.g., a room ID), to prevent reuse
        of tokens generated for other contexts.

    'kw':
        the values to be encoded into the token.

    Returns:
        a URL-safe string representation of the token, signed using our
        secret key.  The token will contain a timestamp, which can be used
        to verify token age (see 'validate_url_safe_token').
    """
    serializer = id_url_safe.URLSafeTimedSerializer(
        secret_key=secret_key,
        salt=salt,
    )
    return serializer.dumps(kw)


def validate_url_safe_token(
    secret_key: str, salt: str, token: str, max_age: int = None
) -> dict:
    """Validate a signed token for a given context

    'secret_key':
        Key use for symmetric encryption of the token.

    'salt':
        the "context" for the token (e.g., a room ID), to prevent reuse of
        tokens generated for other contexts.

    'token':
        the generated URL-safe token (see 'generate_url_safe_token')

    'max_age':
        the maximum age, in seconds, for the token.

    Returns
        a dict unpacked after verifying the token's signature.
        using our secret key;  if the token cannot be verified, returns
        'None'.
    """
    serializer = id_url_safe.URLSafeTimedSerializer(
        secret_key=secret_key,
        salt=salt,
    )

    ok, found = serializer.loads_unsafe(token, max_age=max_age)

    if ok:
        return found


class FastMCPTokenProvider(fmcp_server_auth.TokenVerifier):
    room_id: str
    max_age: int = None

    def __init__(
        self,
        room_id: str,
        the_installation: installation.Installation,
        max_age: int = None,
    ):
        self.room_id = room_id
        self.max_age = max_age
        self.auth_disabled = the_installation.auth_disabled
        self.secret_key = the_installation.get_secret("URL_SAFE_TOKEN_SECRET")

        super().__init__()

    async def verify_token(
        self,
        token: str,
    ) -> mcp_auth_provider.AccessToken | None:
        if self.auth_disabled:
            validated = token
        else:
            validated = validate_url_safe_token(
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
