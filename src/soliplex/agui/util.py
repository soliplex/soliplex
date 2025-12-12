import datetime
import uuid


def _make_uuid_str() -> str:
    return str(uuid.uuid4())


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)  # noqa UP07
