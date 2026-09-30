import sys
from datetime import timezone

import pytest

from gpx_player.validator import GPXValidationError, main as validator_main, parse_timestamp, validate_gpx

def test_validate_gpx_file():
    gpx_file_path = "./example-data/osm-demo-Yury.gpx"
    assert validate_gpx(gpx_file_path, strict=True) is True

    # raises in the `--strict` mode
    # gpx_file_path = "./example-data/osm-demo-Alex.gpx"
    # pytest.raises(GPXValidationError, validate_gpx, gpx_file_path, strict=True)
    # assert validate_gpx(gpx_file_path, strict=False) is True

    # duplicate timestamps: expecting a duplicate timestamp error
    gpx_file_path = "./example-data/duplicate-timestamps.gpx"
    with pytest.raises(GPXValidationError, match="Duplicate timestamp found"):
        validate_gpx(gpx_file_path, strict=True)

    # Timestamps not strictly increasing
    gpx_file_path = "./example-data/wrong-timestamp-order.gpx"
    with pytest.raises(GPXValidationError, match="Timestamps not strictly increasing:"):
        validate_gpx(gpx_file_path, strict=True)


def _write_gpx(tmp_path, version_attr):
    """Write a minimal single-point GPX whose root carries ``version_attr`` verbatim."""
    gpx = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gpx {version_attr} creator="tests" xmlns="http://www.topografix.com/GPX/1/1">\n'
        '  <trk><trkseg>\n'
        '    <trkpt lat="53.5" lon="9.8"><time>2024-06-15T14:33:04Z</time></trkpt>\n'
        '  </trkseg></trk>\n'
        '</gpx>\n'
    )
    path = tmp_path / "versioned.gpx"
    path.write_text(gpx, encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    ("version_attr", "expected"),
    [
        ('version="9.9"', "Unsupported or missing GPX version: 9.9"),
        ("", "Unsupported or missing GPX version: None"),
    ],
    ids=["unsupported-version", "missing-version"],
)
def test_validate_gpx_bad_version_raises_typed_error(tmp_path, version_attr, expected):
    gpx_file_path = _write_gpx(tmp_path, version_attr)

    with pytest.raises(GPXValidationError, match=expected):
        validate_gpx(gpx_file_path)


def test_validate_gpx_cli_reports_typed_validation_failure(tmp_path, monkeypatch, capsys):
    path = _write_gpx(tmp_path, 'version="9.9"')
    monkeypatch.setattr(sys, "argv", ["gpx-validate", path])

    with pytest.raises(SystemExit) as excinfo:
        validator_main()

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Unsupported or missing GPX version: 9.9" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2024-06-15T14:46:21Z", "2024-06-15T14:46:21+00:00"),
        ("2024-06-15T14:46:21.123456Z", "2024-06-15T14:46:21.123456+00:00"),
        ("2024-06-15T16:46:21.123456+02:00", "2024-06-15T14:46:21.123456+00:00"),
        ("2024-06-15T16:46:21+0200", "2024-06-15T14:46:21+00:00"),
    ],
)
def test_parse_timestamp_normalizes_aware_iso_values_to_utc(timestamp, expected):
    parsed = parse_timestamp(timestamp)

    assert parsed.isoformat() == expected
    assert parsed.tzinfo is timezone.utc


def test_parse_timestamp_rejects_naive_values():
    with pytest.raises(ValueError, match="timezone-aware"):
        parse_timestamp("2024-06-15T14:46:21.123456")


def _write_timed_points(tmp_path, timestamps):
    points = "".join(
        f'<trkpt lat="53.5" lon="9.8">{f"<time>{timestamp}</time>" if timestamp is not None else ""}</trkpt>'
        for timestamp in timestamps
    )
    path = tmp_path / "track.gpx"
    path.write_text(
        '<gpx version="1.1" creator="tests" xmlns="http://www.topografix.com/GPX/1/1">'
        f'<trk><name>Test boat</name><trkseg>{points}</trkseg></trk></gpx>',
        encoding="utf-8",
    )
    return path


def test_validate_gpx_accepts_schema_valid_missing_trackpoint_time(tmp_path):
    path = _write_timed_points(tmp_path, [None])

    assert validate_gpx(path, strict=True) is True


def test_validate_gpx_rejects_naive_trackpoint_time_as_typed_error(tmp_path):
    path = _write_timed_points(tmp_path, ["2024-06-15T14:46:21"])

    with pytest.raises(GPXValidationError, match="timezone-aware"):
        validate_gpx(path, strict=True)


def test_validate_gpx_compares_offset_timestamps_as_utc_instants(tmp_path):
    path = _write_timed_points(
        tmp_path,
        ["2024-06-15T14:46:21Z", "2024-06-15T16:46:21+02:00"],
    )

    with pytest.raises(GPXValidationError, match="Duplicate timestamp found"):
        validate_gpx(path, strict=True)
