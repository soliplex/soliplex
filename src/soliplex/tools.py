import datetime


async def get_current_datetime() -> str:
    """
    Get the current date and time in ISO format.

    Returns:
        str: Current datetime in ISO format with timezone information.
    """
    return datetime.datetime.now(datetime.UTC).isoformat()

