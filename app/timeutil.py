"""Time helpers. All timestamps in the source data are treated as IST (Asia/Kolkata)."""
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def parse_ist(value):
    """Parse a value into a timezone-aware IST datetime. Empty or NULL returns None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text == "" or text.upper() == "NULL":
            return None
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def hours_between(start, end):
    if start is None or end is None:
        return None
    return (end - start).total_seconds() / 3600.0
