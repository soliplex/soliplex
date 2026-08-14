import colorsys
import datetime
import uuid

# Successive multiples of the golden angle land far apart on the hue
# circle and never repeat, so labels created back to back look distinct
# without keeping any palette state.
_GOLDEN_ANGLE_DEGREES = 137.508

# Mid saturation and lightness, so the same swatch stays legible against
# both the light and the dark theme; the client derives its own on-color.
_LABEL_SATURATION = 0.65
_LABEL_LIGHTNESS = 0.55


def _make_uuid_str() -> str:
    return str(uuid.uuid4())


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)  # noqa UP07


def hue_rotated_hex(index: int) -> str:
    """Return a '#RRGGBB' color for 'index', rotating hue by the golden angle.

    Deterministic in 'index', so a label keeps its color for as long as
    it keeps its ID. Callers pass the row's own primary key rather than a
    count of existing rows: a count repeats itself after a delete and
    races concurrent creates, while the key does neither.
    """
    hue = (index * _GOLDEN_ANGLE_DEGREES) % 360.0
    red, green, blue = colorsys.hls_to_rgb(
        hue / 360.0,
        _LABEL_LIGHTNESS,
        _LABEL_SATURATION,
    )
    return (
        f"#{round(red * 255):02X}"
        f"{round(green * 255):02X}"
        f"{round(blue * 255):02X}"
    )
