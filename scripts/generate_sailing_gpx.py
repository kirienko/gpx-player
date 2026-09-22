#!/usr/bin/env python3
"""Generate a synthetic sailing GPX track that looks like a real Strava recording.

The boat sails a simple course (beat to a windward mark, reach, broad reach
home) around a start point, tacking and gybing where needed. Speed follows a
small polar diagram with gusts and a lag through manoeuvres, so it never
exceeds ``--max-speed`` knots. The output mimics the demo files in
``example-data/``: irregular 3-6 s sampling, GPS jitter, ``atemp`` and ``hr``
extensions.

Example:

    python scripts/generate_sailing_gpx.py --lat 36.406762 --lon 30.486631 \\
        --start 2026-09-22T14:12:07+03:00 --output example-data/synthetic-sail-cirali.gpx
"""
import argparse
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

KNOT = 0.514444  # m/s
EARTH_M_PER_DEG = 111_320.0

GPX_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd \
http://www.garmin.com/xmlschemas/GpxExtensions/v3 http://www.garmin.com/xmlschemas/GpxExtensionsv3.xsd \
http://www.garmin.com/xmlschemas/TrackPointExtension/v1 http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd" \
creator="StravaGPX" version="1.1" xmlns="http://www.topografix.com/GPX/1/1" \
xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" \
xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3">
 <metadata>
  <time>{time}</time>
 </metadata>
 <trk>
  <name>{name}</name>
  <type>Sail</type>
  <trkseg>
"""

GPX_POINT = """   <trkpt lat="{lat:.7f}" lon="{lon:.7f}">
    <ele>{ele:.1f}</ele>
    <time>{time}</time>
    <extensions>
     <gpxtpx:TrackPointExtension>
      <gpxtpx:atemp>{atemp}</gpxtpx:atemp>
      <gpxtpx:hr>{hr}</gpxtpx:hr>
     </gpxtpx:TrackPointExtension>
    </extensions>
   </trkpt>
"""

GPX_FOOTER = """  </trkseg>
 </trk>
</gpx>
"""


def angle_diff(a, b):
    """Signed smallest difference a - b in degrees, in (-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


def polar(twa):
    """Fraction of top speed at a true wind angle (0..180 degrees)."""
    twa = abs(twa)
    table = [(0, 0.05), (30, 0.15), (40, 0.62), (45, 0.76), (60, 0.88),
             (90, 1.0), (110, 1.0), (135, 0.9), (150, 0.8), (180, 0.7)]
    for (a0, v0), (a1, v1) in zip(table, table[1:]):
        if twa <= a1:
            return v0 + (v1 - v0) * (twa - a0) / (a1 - a0)
    return table[-1][1]


def offset(bearing_deg, dist_m):
    """(x east, y north) of a point dist_m away along bearing_deg."""
    r = math.radians(bearing_deg)
    return dist_m * math.sin(r), dist_m * math.cos(r)


def simulate(rng, wind_from, top_speed_kn, max_speed_kn, scale):
    """Sail the course and return a list of (t_seconds, x, y, speed_ms, manoeuvring)."""
    wx, wy = offset(wind_from, 2600 * scale)
    course = [
        ((350 * scale, 60 * scale), "leave", 2.2),   # ghost out from the mooring
        ((wx, wy), "beat", None),                    # windward mark
        ((wx + 150 * scale, wy + 2200 * scale), "reach", None),
        ((250 * scale, 150 * scale), "home", None),  # broad reach back
        ((0.0, 0.0), "moor", 1.6),                   # creep back to the mooring
    ]

    x = y = 0.0
    heading = 90.0
    speed = 0.3
    t = 0
    tack_side = 1        # +1 starboard offset from the wind, -1 port
    leg_start = (x, y)
    shift = 0.0          # slow oscillating wind shift
    gust = 1.0           # Ornstein-Uhlenbeck gust factor
    samples = []

    for (mx, my), kind, speed_cap in course:
        leg_start = (x, y)
        while math.hypot(mx - x, my - y) > 20:
            t += 1
            shift += (-shift * 0.002) + rng.gauss(0, 0.25)
            gust += (1.0 - gust) * 0.02 + rng.gauss(0, 0.012)
            gust = min(max(gust, 0.8), 1.08)
            wind = wind_from + shift

            bearing = math.degrees(math.atan2(mx - x, my - y)) % 360
            twa_mark = angle_diff(bearing, wind)
            desired = bearing
            if abs(twa_mark) < 44:
                # Beating: sail close-hauled, tack on the layline or at the corridor edge.
                close = 44
                lx, ly = mx - leg_start[0], my - leg_start[1]
                leg_len = math.hypot(lx, ly) or 1.0
                cross = ((x - leg_start[0]) * ly - (y - leg_start[1]) * lx) / leg_len
                corridor = 220 * scale
                if twa_mark * tack_side < -close + 2 or cross * tack_side > corridor:
                    tack_side = -tack_side
                desired = wind + tack_side * close
            elif abs(twa_mark) > 155:
                # Dead run: gybe downwind at 150 degrees instead.
                if twa_mark * tack_side < 0 and abs(twa_mark) < 170:
                    tack_side = -tack_side
                desired = wind + tack_side * 150
            else:
                tack_side = 1 if twa_mark > 0 else -1

            turn = angle_diff(desired, heading)
            heading = (heading + max(-7.0, min(7.0, turn))) % 360
            manoeuvring = abs(turn) > 20

            twa = angle_diff(heading, wind)
            target = top_speed_kn * polar(twa) * gust
            if speed_cap is not None:
                target = min(target, speed_cap)
            dist_to_mark = math.hypot(mx - x, my - y)
            if kind == "moor" and dist_to_mark < 120:
                target = min(target, 0.6 + dist_to_mark / 120)
            target = min(target, max_speed_kn) * KNOT
            speed += (target - speed) / 9.0

            dx, dy = offset(heading, speed)
            # A little surface drift with the wind.
            lx, ly = offset(wind + 180, 0.02)
            x += dx + lx
            y += dy + ly
            samples.append((t, x, y, speed, manoeuvring))
    return samples


def to_trackpoints(rng, samples, lat0, lon0, start):
    """Resample irregularly like a phone logger and add GPS noise."""
    m_per_deg_lon = EARTH_M_PER_DEG * math.cos(math.radians(lat0))
    points = []
    nx = ny = 0.0
    hr = 92.0
    atemp = 30.0
    next_t = 0
    last_manoeuvre = -999
    for t, x, y, speed, manoeuvring in samples:
        if manoeuvring:
            last_manoeuvre = t
        if t < next_t:
            continue
        next_t = t + rng.choice([3, 4, 4, 5, 5, 5, 6])
        if rng.random() < 0.01:
            next_t += rng.randint(6, 12)  # occasional logging gap
        # Slowly wandering GPS error, small enough not to inflate point speeds.
        nx = 0.9 * nx + rng.gauss(0, 0.25)
        ny = 0.9 * ny + rng.gauss(0, 0.25)
        effort = 118 if t - last_manoeuvre < 40 else 96 + 12 * speed / (5.5 * KNOT)
        hr += (effort - hr) * 0.15 + rng.gauss(0, 1.2)
        atemp = min(max(atemp + rng.gauss(0, 0.05), 28.5), 31.4)
        points.append({
            "lat": lat0 + (y + ny) / EARTH_M_PER_DEG,
            "lon": lon0 + (x + nx) / m_per_deg_lon,
            "ele": rng.gauss(0.0, 0.6),
            "time": (start + timedelta(seconds=t)).astimezone(timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "atemp": round(atemp),
            "hr": int(round(hr)),
        })
    return points


def positive_finite(value):
    """argparse type for a positive, finite float."""
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lat", type=float, default=36.406762, help="start latitude")
    parser.add_argument("--lon", type=float, default=30.486631, help="start longitude")
    parser.add_argument("--start", default=None,
                        help="ISO start time with offset (default: today 14:12 UTC+3)")
    parser.add_argument("--duration", type=positive_finite, default=60.0,
                        help="approximate duration in minutes (default: 60)")
    parser.add_argument("--wind-from", type=float, default=120.0,
                        help="true wind direction in degrees (default: 120, sea breeze)")
    parser.add_argument("--max-speed", type=positive_finite, default=5.4,
                        help="boat speed cap in knots (default: 5.4)")
    parser.add_argument("--name", default="Çıralı Afternoon Sail")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("synthetic-sail.gpx"))
    args = parser.parse_args()

    if args.start:
        start = datetime.fromisoformat(args.start)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    else:
        tz = timezone(timedelta(hours=3))
        start = datetime.now(tz).replace(hour=14, minute=12, second=7, microsecond=0)

    # Scale the course until the simulated sail matches the requested duration.
    scale = 1.0
    for _ in range(6):
        samples = simulate(random.Random(args.seed), args.wind_from, 5.7,
                           args.max_speed, scale)
        scale *= args.duration * 60 / samples[-1][0]
    points = to_trackpoints(random.Random(args.seed + 1), samples,
                            args.lat, args.lon, start)

    with args.output.open("w", encoding="utf-8") as f:
        f.write(GPX_HEADER.format(time=points[0]["time"], name=escape(args.name)))
        for p in points:
            f.write(GPX_POINT.format(**p))
        f.write(GPX_FOOTER)
    minutes = samples[-1][0] / 60
    print(f"Wrote {args.output}: {len(points)} points, {minutes:.1f} min")


if __name__ == "__main__":
    main()
