from typing import List, Optional, Tuple

import gpxpy.geo


DEFAULT_MAX_SPEED_KNOTS = 12.0


def same_track_segment(start: dict, end: dict) -> bool:
    return start.get("segment_index", 0) == end.get("segment_index", 0)


def edge_metrics(
    points: List[dict], max_speed: float
) -> List[Optional[Tuple[float, float, float]]]:
    edges = []
    for i in range(1, len(points)):
        start, end = points[i - 1], points[i]
        if not same_track_segment(start, end):
            edges.append(None)
            continue
        time_diff = (end["time"] - start["time"]).total_seconds()
        if time_diff <= 0:
            edges.append(None)
            continue
        distance = gpxpy.geo.haversine_distance(
            start["lat"],
            start["lon"],
            end["lat"],
            end["lon"],
        )
        speed = (distance / time_diff) * 1.94384
        edges.append((distance, time_diff, speed) if speed <= max_speed else None)
    return edges
