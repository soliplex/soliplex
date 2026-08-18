import datetime
import uuid

# The color a label carries until somebody chooses one for it.
#
# Neutral in the strict sense -- no hue at all -- so a label nobody has
# colored reads as uncolored rather than as one more hue competing with
# the rest. A per-label hue assigned on the label's behalf cannot do
# that: every new label would arrive already shouting, and there would
# be no way to say "no color" afterwards. The client offers this same
# value as the first swatch in its picker, so a label can be returned to
# it.
DEFAULT_LABEL_COLOR = "#808080"


def _make_uuid_str() -> str:
    return str(uuid.uuid4())


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)  # noqa UP07
