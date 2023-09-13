import datetime as dt
import math
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


def haversine_distance(lat1, lon1, lat2, lon2) -> int:
    # Geodetic distance between two points, in km
    R = 6371.0  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def km_to_nm(dist: float) -> float:
    return dist/1.852