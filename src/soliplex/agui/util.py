import datetime
import uuid


def _make_uuid_str() -> str:
    return str(uuid.uuid4())


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)  # noqa UP07


def _epoch_ms(value: datetime.datetime) -> int:
    """Whole milliseconds since the Unix epoch.

    Naive values are assumed to be UTC, matching how the backend writes
    timestamps and how SQLite returns them (without zone) on read.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.UTC)
    return int(value.timestamp() * 1000)
