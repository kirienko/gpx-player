import datetime as dt
import shutil
from pathlib import Path

from gpx_player.utils import slug, timedelta_to_hms
from gpx_player.gpx_utils import remove_extensions_tags

def test_slug():
    # Test cases for the slug function
    test_cases = [
        ("Hello World!", "hello-world"),
        ("Python_3.9", "python_39"),
        ("   Leading and trailing spaces   ", "leading-and-trailing-spaces"),
        ("Special #$%&* characters!", "special-characters"),
        ("Multiple   Spaces", "multiple-spaces"),
        ("", ""),
    ]
    for input_str, expected_output in test_cases:
        assert slug(input_str) == expected_output

def test_timedelta_to_hms():
    # Test cases for the timedelta_to_hms function
    test_cases = [
        (dt.timedelta(hours=1, minutes=30, seconds=15), "1:30:15"),
        (dt.timedelta(minutes=45, seconds=5), "45:05"),
        (dt.timedelta(seconds=59), "00:59"),
        (dt.timedelta(hours=2), "2:00:00"),
        (dt.timedelta(hours=0, minutes=0, seconds=0), "00:00"),
        (dt.timedelta(hours=30, minutes=0, seconds=0), "30:00:00"),
        (dt.timedelta(hours=23, minutes=59, seconds=59), "23:59:59"),
    ]
    for td, expected_output in test_cases:
        assert timedelta_to_hms(td) == expected_output


def test_remove_extensions_tags(tmp_path):
    src = Path("example-data/track1.gpx")
    tmp_file = tmp_path / src.name
    shutil.copy(src, tmp_file)

    cleaned, count = remove_extensions_tags(str(tmp_file))

    assert count == 511
    with open(cleaned, "r") as f:
        content = f.read()
        assert "<extensions>" not in content


def test_remove_extensions_tags_noop(tmp_path):
    data = """<?xml version='1.1'?>\n<gpx version='1.1'><trk></trk></gpx>"""
    gpx_file = tmp_path / "sample.gpx"
    gpx_file.write_text(data)

    cleaned, count = remove_extensions_tags(str(gpx_file))

    assert count == 0
    with open(cleaned) as f:
        assert "<extensions>" not in f.read()


def test_remove_extensions_tags_preserve_namespace(tmp_path):
    src = Path("example-data/track1.gpx")
    dst = tmp_path / src.name
    shutil.copy(src, dst)

    cleaned, _ = remove_extensions_tags(str(dst))

    with open(cleaned) as f:
        f.readline()  # XML declaration
        second = f.readline()

    assert "<ns0:gpx" not in second


def test_remove_extensions_tags_overwrite(tmp_path):
    src = Path("example-data/track1.gpx")
    dst = tmp_path / src.name
    shutil.copy(src, dst)

    cleaned, removed = remove_extensions_tags(str(dst), overwrite=True)

    assert removed == 511
    assert cleaned == str(dst)
    with open(dst) as f:
        assert "<extensions>" not in f.read()
