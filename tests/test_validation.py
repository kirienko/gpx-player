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
def test_validate_gpx_bad_version_exits_with_stderr(tmp_path, capsys, version_attr, expected):
    """An unsupported or missing root ``version`` exits 1 and reports on stderr.

    This branch calls ``sys.exit()`` rather than raising ``GPXValidationError``,
    so callers embedding the validator have to catch ``SystemExit`` too. The
    message must not go to stdout, which is reserved for the progress output of
    a successful run.
    """
    gpx_file_path = _write_gpx(tmp_path, version_attr)

    with pytest.raises(SystemExit) as excinfo:
        validate_gpx(gpx_file_path)

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert expected in captured.err
    assert captured.out == ""
