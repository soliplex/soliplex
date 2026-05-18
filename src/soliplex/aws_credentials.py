"""Bridge AWS credentials into ``lancedb`` ``storage_options``.

Lance-io reads AWS credentials from ``os.environ`` directly. Soliplex's
``.env`` handling keeps values in the installation config and does not
mutate ``os.environ``, so credentials placed there never reach lance.
When the optional ``botocore`` dependency is installed (``soliplex[aws]``),
this module resolves credentials via botocore's default provider chain
(env vars, ``~/.aws/credentials``, ``AWS_PROFILE``, SSO cache, EC2/ECS/EKS
instance role) and returns them shaped for ``lancedb`` ``storage_options``.

The resolver is re-called on every ``haiku_rag_config`` access (see
``soliplex.config.rag``); refreshable credentials (SSO, AssumeRole, IMDS)
re-fetch automatically inside ``get_frozen_credentials`` when they expire.
"""

from __future__ import annotations

import typing


def resolve_aws_storage_options() -> dict[str, str]:
    """Return AWS creds shaped for ``lancedb.storage_options``, or {}.

    Returns an empty dict if ``botocore`` is not installed or no
    credentials are available from the default provider chain.
    """
    try:
        import botocore.session
    except ImportError:
        return {}

    session = _get_session(botocore.session.get_session)
    creds = session.get_credentials()
    if creds is None:
        return {}

    frozen = creds.get_frozen_credentials()
    result: dict[str, str] = {
        "aws_access_key_id": frozen.access_key,
        "aws_secret_access_key": frozen.secret_key,
    }
    if frozen.token:
        result["aws_session_token"] = frozen.token

    region = session.get_config_variable("region")
    if region:
        result["region"] = region

    return result


_SESSION: typing.Any = None


def _get_session(factory):
    """Return a cached botocore session built by 'factory'.

    Caching the session preserves botocore's internal credential-provider
    cache (and the ``RefreshableCredentials`` it returns) across calls, so
    refresh-on-expiry works without us tracking expirations ourselves.
    """
    global _SESSION
    if _SESSION is None:
        _SESSION = factory()
    return _SESSION
