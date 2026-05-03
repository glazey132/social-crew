"""Parse user-facing time strings into seconds."""

from __future__ import annotations


def _non_negative_int(tok: str, *, label: str) -> int:
    s = tok.strip()
    try:
        v = float(s)
    except ValueError as e:
        raise ValueError(f"invalid {label}: {tok!r}") from e
    if v < 0 or int(v) != v:
        raise ValueError(f"invalid {label} (must be a non-negative integer): {tok!r}")
    return int(v)


def parse_time_seconds(value: str) -> float:
    """
    Interpret ``value`` as total seconds:

    - No colon: plain float (e.g. ``"3661"``, ``"90.25"``).
    - One colon: ``MM:SS`` — non-negative integer minutes, seconds may include a fractional part.
    - Two colons: ``H:MM:SS`` — integer hours and minutes (minutes < 60), seconds may fraction.

    Leading/trailing whitespace is stripped.
    Raises ``ValueError`` on invalid input or negative time.
    """
    s = value.strip()
    if not s:
        raise ValueError("empty time string")

    if ":" not in s:
        t = float(s)
        if t < 0:
            raise ValueError("negative time")
        return float(t)

    parts = s.split(":")
    if len(parts) > 3 or len(parts) < 2:
        raise ValueError(f"unsupported time format: {value!r}")

    if len(parts) == 2:
        mm = _non_negative_int(parts[0], label="minutes")
        ss = float(parts[1].strip())
        if ss < 0:
            raise ValueError("negative time")
        t = mm * 60 + ss
    else:
        h = _non_negative_int(parts[0], label="hours")
        mm = _non_negative_int(parts[1], label="minutes")
        if mm >= 60:
            raise ValueError(f"minutes must be < 60 in H:MM:SS: {value!r}")
        sec = float(parts[2].strip())
        if sec < 0:
            raise ValueError("negative time")
        t = h * 3600 + mm * 60 + sec

    if t < 0:
        raise ValueError("negative time")
    return float(t)
