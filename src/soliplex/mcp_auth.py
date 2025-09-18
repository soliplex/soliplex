import os

from itsdangerous import url_safe as id_url_safe

URL_SAFE_TOKEN_SECRET_ENV = "SOLIPLEX_URL_SAFE_TOKEN_SECRET"


def get_url_safe_token_secret():
    return os.environ[URL_SAFE_TOKEN_SECRET_ENV]


def generate_url_safe_token(salt: str, **kw) -> str:
    """Generate a signed token for a given context

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
        secret_key=get_url_safe_token_secret(),
        salt=salt,
    )
    return serializer.dumps(kw)


def validate_url_safe_token(salt: str, token: str, max_age: int=None) -> dict:
    """Validate a signed token for a given context

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
        secret_key=get_url_safe_token_secret(),
        salt=salt,
    )

    ok, found = serializer.loads_unsafe(token, max_age=max_age)

    if ok:
        return found
