import datetime as dt
import math
import re

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


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


def decimal_to_dms(value: float) -> str:
    degrees = int(value)
    submin = abs(value - degrees) * 60
    minutes = int(submin)
    seconds = int((submin - minutes) * 60)
    return f"{degrees}°{minutes}'{seconds}\""

def format_func(value, tick_number):
    # a custom ticker formatter function
    return decimal_to_dms(value)


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    # Geodetic distance between two points, in km
    R = 6371.0  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def km_to_nm(dist: float) -> float:
    return dist/1.852

def gen_arrow_head_marker(rot: float) -> (mpl.path.Path, float):
    """generate a marker to plot with matplotlib scatter, plot, ...

    https://matplotlib.org/stable/api/markers_api.html#module-matplotlib.markers
    
    Source: https://stackoverflow.com/a/66973317/4222580
    
    rot=0: positive x direction
    Parameters
    ----------
    rot : float
        rotation in degree
        0 is positive x direction

    Returns
    -------
    arrow_head_marker : Path
        use this path for marker argument of plt.scatter
    scale : float
        multiply a argument of plt.scatter with this factor got get markers
        with the same size independent of their rotation.
        Paths are autoscaled to a box of size -1 <= x, y <= 1 by plt.scatter
    """
    arr = np.array([[.1, .3], [.1, -.3], [1, 0], [.1, .3]])  # arrow shape
    angle = rot / 180 * np.pi
    rot_mat = np.array([
        [np.cos(angle), np.sin(angle)],
        [-np.sin(angle), np.cos(angle)]
    ])
    arr = np.matmul(arr, rot_mat)  # rotates the arrow

    # scale
    x0 = np.amin(arr[:, 0])
    x1 = np.amax(arr[:, 0])
    y0 = np.amin(arr[:, 1])
    y1 = np.amax(arr[:, 1])
    scale = np.amax(np.abs([x0, x1, y0, y1]))
    codes = [mpl.path.Path.MOVETO, mpl.path.Path.LINETO,mpl.path.Path.LINETO, mpl.path.Path.CLOSEPOLY]
    arrow_head_marker = mpl.path.Path(arr, codes)
    
    return arrow_head_marker, scale