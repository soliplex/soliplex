"""Bridge AWS credentials into ``lancedb`` ``storage_options``.

Lance-io reads AWS credentials from ``os.environ`` directly, and
botocore's default provider chain does the same.  Soliplex's ``.env``
handling keeps values in the installation config (``_from_dotenv``)
and does not mutate ``os.environ``, so credentials placed there never
reach lance or botocore.

When the optional ``botocore`` dependency is installed
(``soliplex[aws]``), this module:

1. Bridges any AWS environment variables found in the supplied
   ``extra_env`` (typically the installation's ``.env`` values) into
   ``os.environ`` (using ``setdefault`` so it never overrides values
   the user has already exported).
2. Resolves credentials via botocore's default provider chain — env
   vars (now including the bridged ``.env`` values),
   ``~/.aws/credentials``, ``AWS_PROFILE``, SSO cache, and EC2/ECS/EKS
   instance roles.
3. Returns the resolved credentials shaped for ``lancedb``
   ``storage_options``.

The resolver is re-called on every ``haiku_rag_config`` access (see
``soliplex.config.rag``); refreshable credentials (SSO, AssumeRole,
IMDS) re-fetch automatically inside ``get_frozen_credentials`` when
they expire.

**Region caveat:** lance requires ``region`` in ``storage_options`` to
address S3 — without it, lance often fails with "Bucket not found"
even when credentials are valid.  Neither raw botocore nor boto3's
``Session.region_name`` reads ``AWS_REGION`` (they only read
``AWS_DEFAULT_REGION`` / profile config).  ``_resolve_region`` below
checks both env vars explicitly so a ``.env``-supplied ``AWS_REGION``
reaches lance.  Make sure one of ``AWS_REGION`` /
``AWS_DEFAULT_REGION`` is set somewhere botocore (or our bridge) can
find it.
"""

from __future__ import annotations

import logging
import os
import typing

logger = logging.getLogger(__name__)


# AWS env vars that the AWS SDKs (and lance) read directly from
# ``os.environ``.  When found in a soliplex ``.env`` file, these are
# bridged into the process environment so both botocore and lance can
# see them.
_BRIDGED_AWS_ENV_KEYS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_PROFILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE",
    "AWS_ROLE_ARN",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ENDPOINT_URL",
    "AWS_ENDPOINT_URL_S3",
)


def resolve_aws_storage_options(
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return AWS creds shaped for ``lancedb.storage_options``, or {}.

    Returns an empty dict if ``boto3`` is not installed or no
    credentials are available from the default provider chain.

    ``extra_env`` is an optional supplementary mapping (typically the
    installation's ``.env`` values).  Any AWS-related keys present
    there are bridged into ``os.environ`` (via ``setdefault``) so that
    botocore's ``EnvProvider`` and lance's S3 backend can both see
    them.
    """
    bridged = _bridge_aws_env_to_environ(extra_env or {})
    if bridged:
        logger.info(
            "AWS env bridged from installation .env to os.environ: %s",
            sorted(bridged),
        )

    try:
        import botocore.session
    except ImportError:
        logger.warning(
            "botocore not installed; cannot resolve AWS credentials "
            "for S3 LanceDB. Install with 'uv add soliplex[aws]' or "
            "set lancedb.storage_options explicitly in haiku.rag.yaml."
        )
        return {}

    session = _get_session(botocore.session.get_session)
    creds = session.get_credentials()
    if creds is None:
        logger.warning(
            "No AWS credentials found via botocore's default chain "
            "(env vars, ~/.aws/credentials, AWS_PROFILE, SSO cache, "
            "EC2/ECS/EKS instance role)."
        )
        return {}

    frozen = creds.get_frozen_credentials()
    result: dict[str, str] = {
        "aws_access_key_id": frozen.access_key,
        "aws_secret_access_key": frozen.secret_key,
    }
    if frozen.token:
        result["aws_session_token"] = frozen.token

    region = _resolve_region(session)
    if region:
        result["region"] = region
    else:
        logger.warning(
            "No AWS region found (checked botocore "
            "session.get_config_variable('region'), AWS_REGION env, "
            "AWS_DEFAULT_REGION env). Lance will likely fail with "
            "'Bucket not found' — set AWS_REGION in your .env or "
            "installation environment, or pin lancedb.storage_options "
            "region in haiku.rag.yaml."
        )

    logger.info(
        "Resolved AWS storage_options for lancedb (keys: %s)",
        sorted(result),
    )
    return result


def _resolve_region(session) -> str | None:
    """Return an AWS region from the most-likely-set source, else None.

    Lance / object_store requires an explicit ``region`` in
    ``storage_options`` to address the right S3 endpoint — without it,
    lance often fails with "Bucket not found" even when credentials are
    valid.

    Neither raw ``botocore`` nor ``boto3.session.Session().region_name``
    reads ``AWS_REGION``; both only read ``AWS_DEFAULT_REGION`` (or the
    active profile config).  We check both env vars explicitly so a
    ``.env``-supplied ``AWS_REGION`` reaches lance.
    """
    region = session.get_config_variable("region")
    if region:
        return region

    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")


def _bridge_aws_env_to_environ(extra_env: dict[str, str]) -> list[str]:
    """Copy known AWS_* keys from 'extra_env' into 'os.environ'.

    Existing ``os.environ`` values are never overwritten — explicit
    shell-level configuration always wins.  Returns the list of keys
    actually set, so callers can log what happened.
    """
    bridged: list[str] = []
    for key in _BRIDGED_AWS_ENV_KEYS:
        value = extra_env.get(key)
        if value and key not in os.environ:
            os.environ[key] = value
            bridged.append(key)
    return bridged


_SESSION: typing.Any = None


def _get_session(factory):
    """Return a cached botocore session built by 'factory'.

    Caching the session preserves botocore's internal credential-
    provider cache (and the ``RefreshableCredentials`` it returns)
    across calls, so refresh-on-expiry works without us tracking
    expirations ourselves.
    """
    global _SESSION
    if _SESSION is None:
        _SESSION = factory()
    return _SESSION
