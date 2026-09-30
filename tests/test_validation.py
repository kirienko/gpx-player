import pytest
from lxml import etree

from gpx_player.validator import (
    GPXValidationError,
    validate_coordinates,
    validate_elevations,
    validate_gpx,
    validate_schema,
)

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


def _write_valid_gpx(tmp_path, *, version="1.1", attributes='lat="53.5" lon="9.8"', point_children=None):
    namespace = f"http://www.topografix.com/GPX/{version.replace('.', '/')}"
    if point_children is None:
        point_children = "<ele>12.34</ele><time>2024-06-15T14:33:04Z</time>"
    gpx = (
        f'<gpx version="{version}" creator="tests" xmlns="{namespace}">'
        f"<trk><trkseg><trkpt {attributes}>{point_children}</trkpt></trkseg></trk>"
        "</gpx>"
    )
    path = tmp_path / f"valid-{version.replace('.', '-')}.gpx"
    path.write_text(gpx, encoding="utf-8")
    return str(path)


def _precision_constrained_schema():
    schema_xml = b'''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
        xmlns:g="http://www.topografix.com/GPX/1/1"
        targetNamespace="http://www.topografix.com/GPX/1/1"
        elementFormDefault="qualified">
      <xs:simpleType name="precision2">
        <xs:restriction base="xs:decimal">
          <xs:fractionDigits value="2"/>
        </xs:restriction>
      </xs:simpleType>
      <xs:element name="gpx">
        <xs:complexType><xs:sequence><xs:element name="trkpt">
          <xs:complexType><xs:sequence>
            <xs:element name="ele" type="g:precision2" minOccurs="0"/>
            <xs:element name="other" type="g:precision2" minOccurs="0"/>
          </xs:sequence>
            <xs:attribute name="lat" type="g:precision2" use="required"/>
            <xs:attribute name="lon" type="g:precision2" use="required"/>
          </xs:complexType>
        </xs:element></xs:sequence></xs:complexType>
      </xs:element>
    </xs:schema>'''
    return etree.XMLSchema(etree.fromstring(schema_xml))


def _precision_constrained_tree(*, lat="52.123", lon="13.456", ele="2.789", extra=""):
    root = etree.fromstring(
        f'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trkpt lat="{lat}" lon="{lon}">'
        f"<ele>{ele}</ele>{extra}</trkpt></gpx>".encode()
    )
    return etree.ElementTree(root), root


@pytest.mark.parametrize("strict", [False, True], ids=["lenient", "strict"])
def test_unexpected_element_is_rejected_with_actual_diagnostic(tmp_path, strict, capsys):
    gpx_file = _write_valid_gpx(
        tmp_path,
        point_children="<ele>12.34</ele><time>2024-06-15T14:33:04Z</time><bogus/> ",
    )

    with pytest.raises(GPXValidationError) as excinfo:
        validate_gpx(gpx_file, strict=strict)

    assert "bogus" in str(excinfo.value)
    assert "precision issues" not in capsys.readouterr().out


def test_missing_required_coordinate_attribute_is_rejected_in_lenient_mode(tmp_path):
    gpx_file = _write_valid_gpx(tmp_path, attributes='lon="9.8"')

    with pytest.raises(GPXValidationError, match="lat"):
        validate_gpx(gpx_file)


def test_out_of_order_point_elements_are_rejected_in_lenient_mode(tmp_path):
    gpx_file = _write_valid_gpx(
        tmp_path,
        point_children="<time>2024-06-15T14:33:04Z</time><ele>12.34</ele>",
    )

    with pytest.raises(GPXValidationError, match="not expected"):
        validate_gpx(gpx_file)


@pytest.mark.parametrize("version", ["1.0", "1.1"])
@pytest.mark.parametrize("strict", [False, True], ids=["lenient", "strict"])
def test_valid_gpx_versions_accept_high_decimal_precision(tmp_path, version, strict):
    gpx_file = _write_valid_gpx(
        tmp_path,
        version=version,
        attributes='lat="53.123456789123" lon="9.876543210987"',
        point_children="<ele>12.123456789123</ele><time>2024-06-15T14:33:04Z</time>",
    )

    assert validate_gpx(gpx_file, strict=strict) is True


def test_lenient_mode_bypasses_only_fraction_digits_errors_on_gpx_numeric_fields(capsys):
    tree, root = _precision_constrained_tree()
    schema = _precision_constrained_schema()

    validate_schema(tree, schema, strict=False, root=root)

    assert "manual checks passed in lenient mode" in capsys.readouterr().out
    with pytest.raises(GPXValidationError, match="strict mode enabled"):
        validate_schema(tree, schema, strict=True, root=root)


@pytest.mark.parametrize(
    ("lat", "lon", "ele", "extra", "message"),
    [
        ("91.123", "13.45", "2.78", "", "Latitude 91.123 out of range"),
        ("52.12", "181.123", "2.78", "", "Longitude 181.123 out of range"),
        ("52.12", "13.45", "not-a-number", "", "not-a-number"),
        ("52.12", "13.45", "2.78", "<bogus/>", "GPX schema"),
    ],
    ids=[
        "out-of-range-latitude",
        "out-of-range-longitude",
        "malformed-elevation",
        "mixed-unknown-element",
    ],
)
def test_lenient_mode_rejects_non_precision_failures(
    lat, lon, ele, extra, message
):
    tree, root = _precision_constrained_tree(lat=lat, lon=lon, ele=ele, extra=extra)
    schema = _precision_constrained_schema()

    with pytest.raises(GPXValidationError) as excinfo:
        validate_schema(tree, schema, strict=False, root=root)

    assert message in str(excinfo.value)


def test_lenient_mode_rejects_precision_errors_on_unrelated_elements():
    tree, root = _precision_constrained_tree(extra="<other>1.234</other>")
    schema = _precision_constrained_schema()

    with pytest.raises(GPXValidationError) as excinfo:
        validate_schema(tree, schema, strict=False, root=root)

    assert "other" in str(excinfo.value)


@pytest.mark.parametrize(
    ("attributes", "point_children", "value"),
    [
        ('lat="NaN" lon="9.8"', "<ele>12.34</ele>", "NaN"),
        ('lat="53.5" lon="9.8"', "<ele>NaN</ele>", "NaN"),
    ],
    ids=["non-finite-latitude", "non-finite-elevation"],
)
def test_lenient_mode_rejects_non_finite_numeric_values(
    tmp_path, attributes, point_children, value
):
    gpx_file = _write_valid_gpx(
        tmp_path, attributes=attributes, point_children=point_children
    )

    with pytest.raises(GPXValidationError) as excinfo:
        validate_gpx(gpx_file)

    assert value.lower() in str(excinfo.value).lower()


@pytest.mark.parametrize(
    ("attributes", "point_children", "check", "message"),
    [
        ('lat="NaN" lon="9.8"', "", validate_coordinates, "must be finite"),
        (
            'lat="53.5" lon="9.8"',
            "<ele>Infinity</ele>",
            validate_elevations,
            "Invalid elevation value",
        ),
    ],
    ids=["non-finite-coordinate", "non-finite-elevation"],
)
def test_manual_numeric_checks_reject_non_finite_values(
    tmp_path, attributes, point_children, check, message
):
    gpx_file = _write_valid_gpx(
        tmp_path, attributes=attributes, point_children=point_children
    )
    root = etree.parse(gpx_file).getroot()

    with pytest.raises(GPXValidationError, match=message):
        check(root)


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
