import pytest
from gpx_player.validator import validate_gpx, GPXValidationError

def test_validate_gpx_file():
    gpx_file_path = "./example-data/osm-demo-Yury.gpx"
    assert validate_gpx(gpx_file_path, strict=True) is True

    # raises in the `--strict` mode
    # gpx_file_path = "./example-data/osm-demo-Alex.gpx"
    # pytest.raises(GPXValidationError, validate_gpx, gpx_file_path, strict=True)
    # assert validate_gpx(gpx_file_path, strict=False) is True

    # duplicate timestamps: expecting a duplicate timestamp error
    gpx_file_path = "./example-data/duplicate-timestamps.gpx"
    with pytest.raises(GPXValidationError, match="Duplicate timestamp found") as excinfo:
        validate_gpx(gpx_file_path, strict=True)

    # Timestamps not strictly increasing
    gpx_file_path = "./example-data/wrong-timestamp-order.gpx"
    with pytest.raises(GPXValidationError, match="Timestamps not strictly increasing:") as excinfo:
        validate_gpx(gpx_file_path, strict=True)
