import datetime as dt
import re


def slug(input_string: str) -> str:
    # Remove non-word characters (everything except numbers and letters)
    s = re.sub(r"[^\w\s]", '', input_string)
    # Replace all runs of whitespace with a single dash
    s = re.sub(r"\s+", '-', s)
    return s.lower()


def timedelta_to_hms(td: dt.timedelta) -> str:
    """ converts timedelta to [hours:]minutes:seconds"""
    total_seconds = int(td.total_seconds())
    # Break down the seconds into hours, minutes, and seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format it, including hours only if they are greater than 0
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes:02}:{seconds:02}"
