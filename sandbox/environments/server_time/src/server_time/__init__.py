"""Hour — a simple module that returns the current server time."""

from datetime import datetime, timezone


def now() -> dict:
    """Return the current server time with timezone information."""
    utc_now = datetime.now(timezone.utc)
    local_now = datetime.now().astimezone()
    results ={
        "utc": utc_now.isoformat(),
        "local": local_now.isoformat(),
        "timezone": str(local_now.tzinfo),
        "offset": local_now.strftime("%z"),
    }

    return results
