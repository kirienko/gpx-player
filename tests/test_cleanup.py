import shutil
from pathlib import Path

import pytest

from gpx_player.clean_gpx import clean_gpx_file
from gpx_player.validator import GPXValidationError


def test_clean_gpx_file(tmp_path):
    src = Path("example-data/track1.gpx")
    temp = tmp_path / src.name
    shutil.copy(src, temp)

    cleaned, removed = clean_gpx_file(str(temp))

    assert removed == 511
    with open(cleaned) as f:
        assert "<extensions>" not in f.read()


def test_clean_gpx_file_overwrite(tmp_path):
    src = Path("example-data/track1.gpx")
    temp = tmp_path / src.name
    shutil.copy(src, temp)

    cleaned, removed = clean_gpx_file(str(temp), overwrite=True)

    assert cleaned == str(temp)
    assert removed == 511
    with open(temp) as f:
        assert "<extensions>" not in f.read()


def test_clean_gpx_file_invalid(tmp_path):
    src = Path("example-data/wrong-timestamp-order.gpx")
    temp = tmp_path / src.name
    shutil.copy(src, temp)

    with pytest.raises(GPXValidationError):
        clean_gpx_file(str(temp))

