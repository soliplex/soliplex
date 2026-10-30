import datetime
import uuid

# The neutral grey a label carries until someone colors it.
DEFAULT_LABEL_COLOR = "#808080"


def _make_uuid_str() -> str:
    return str(uuid.uuid4())


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)
