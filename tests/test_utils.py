import math
from utils import haversine_distance  # assuming the function is saved in a module named 'haversine'

def test_haversine_distance():
    # 1. Meridian piece from (0,0) to (1,0)
    # Since the Earth's radius is approximately 6371 km, 
    # the distance between two latitudinal degrees approximately equals 111 km.
    assert math.isclose(haversine_distance(0, 0, 1, 0), 111, rel_tol=1e-2)

    # 2. Parallel piece from (0,0) to (0,1)
    # At the equator, the distance between two longitudinal degrees is at its maximum, which is approximately 111 km.
    assert math.isclose(haversine_distance(0, 0, 0, 1), 111, rel_tol=1e-2)

    # 3. Distance between Royal Greenwich Observatory and Westminster Abbey
    # Royal Greenwich Observatory: (51.4779° N, 0.0015° W)
    # Westminster Abbey: (51.4994° N, 0.1276° W)
    # The actual distance is approximately 8.7 km.
    print(haversine_distance(51.4779, -0.0015, 51.4994, -0.1276))
    assert math.isclose(haversine_distance(51.4779, -0.0015, 51.4994, -0.1276), 9.05, rel_tol=1e-2)
    