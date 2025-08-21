import argparse
import sys
from datetime import datetime as dt

from lxml import etree

class GPXValidationError(Exception):
    """Exception raised for GPX validation errors."""
    pass


def parse_gpx(file_path):
    try:
        tree = etree.parse(file_path)
    except etree.XMLSyntaxError as e:
        raise GPXValidationError(f"XML Syntax Error: {e}")
    return tree


def parse_timestamp(timestamp_str):
    """
    A helper function that tolerates both `2024-06-15T14:46:21.000Z` and `2024-06-15T14:46:21Z` time formats,
    i.e. both integer and decimal seconds.
    """
    formats = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]
    for fmt in formats:
        try:
            return dt.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Timestamp '{timestamp_str}' does not match any expected format.")


def load_schema(version):
    from pathlib import Path
    if version not in ("1.0", "1.1"):
        raise GPXValidationError(f"Unsupported GPX version: {version}")
    schema_dir = Path(__file__).parent.parent / "schema"
    xsd_path = schema_dir / f"gpx_{version}.xsd"

    try:
        with xsd_path.open('rb') as f:
            schema_doc = etree.parse(f)
            schema = etree.XMLSchema(schema_doc)
    except Exception as e:
        raise GPXValidationError(f"Error loading schema file '{xsd_path}': {e}")
    return schema


def validate_coordinates(root):
    """Custom check for coordinate values in lenient mode."""
    for trkpt in root.findall(".//{*}trkpt"):
        lat = trkpt.get("lat")
        lon = trkpt.get("lon")
        try:
            lat_val = float(lat)
            lon_val = float(lon)
        except (TypeError, ValueError):
            raise GPXValidationError(f"Invalid coordinate values: lat={lat}, lon={lon}")
        if not (-90 <= lat_val <= 90):
            raise GPXValidationError(f"Latitude {lat_val} out of range (-90, 90)")
        if not (-180 <= lon_val <= 180):
            raise GPXValidationError(f"Longitude {lon_val} out of range (-180, 180)")


def validate_elevations(root):
    """Custom check for elevation values in lenient mode."""
    for trkpt in root.findall(".//{*}trkpt"):
        ele_elem = trkpt.find("{*}ele")
        if ele_elem is not None and ele_elem.text:
            try:
                ele_val = float(ele_elem.text)
            except ValueError:
                raise GPXValidationError(f"Invalid elevation value: {ele_elem.text}")


def validate_schema(tree, schema, strict, root=None):
    """
    Validate the XML tree against the provided schema.
    In default (lenient) mode, if errors are solely due to extra precision on coordinates,
    perform a manual coordinate check.
    In strict mode, any schema violation will result in an error.
    """
    if schema.validate(tree):
        return  # Validation passed

    if strict:
        error_messages = "\n".join(f"  {error.message}" for error in schema.error_log[:10])
        raise GPXValidationError(f"XML does not conform to the GPX schema (strict mode enabled):\n"
                                  f"The first {min(10, len(schema.error_log))} errors (out of {len(schema.error_log)}) are:\n"
                                  f"{error_messages}")

    # Lenient mode: check if errors are exclusively about lat/lon or elevation precision

    # Define allowed keywords for lenient errors: latitude, longitude, and elevation.
    allowed_keywords = ["latitudeType", "longitudeType", "ele"]

    # Filter out errors that are solely about these issues.
    error_log = [e.message for e in schema.error_log]
    filtered_errors = [msg for msg in error_log if not any(keyword in msg for keyword in allowed_keywords)]

    if len(filtered_errors) == 0:
        # Run manual coordinate validation
        validate_coordinates(root)
        validate_elevations(root)
        print("Warning: GPX file does not strictly conform to the schema (coordinate precision issues), "
              "but manual checks passed in lenient mode.")
    else:
        error_messages = "\n".join(f"  {error}" for error in filtered_errors[:10])
        raise GPXValidationError(f"XML does not conform to the GPX schema ({len(filtered_errors)} errors):\n"
                                  f"The first {min(10, len(filtered_errors))} errors (out of {len(filtered_errors)}) are:\n"
                                  f"{error_messages}")


def check_timestamp_consistency(root):
    """
    For each track that has at least one timestamped point, ensure that:
      - Timestamps appear in strictly increasing order.
      - No two distinct points have the same timestamp.
    """
    # Using a namespace-agnostic search with {*}
    tracks = root.findall(".//{*}trk")
    if not tracks:
        # No tracks in the file.
        return

    # Iterate over each track.
    for trk in tracks:
        # List to store timestamps (in order) for the current track.
        timestamps = []
        # Process each track segment (trkseg) in the order they appear.
        for trkseg in trk.findall(".//{*}trkseg"):
            for trkpt in trkseg.findall("{*}trkpt"):
                time_elem = trkpt.find("{*}time")
                if time_elem is not None and time_elem.text:
                    try:
                        # GPX timestamps are typically in ISO8601 format ending with 'Z' (UTC).
                        t = parse_timestamp(time_elem.text)
                    except ValueError:
                        print(f"Invalid timestamp format: {time_elem.text}")
                        sys.exit(1)
                    # Check for duplicate timestamp (i.e. same time appears more than once in this track)
                    if t in timestamps:
                        raise GPXValidationError(f"Duplicate timestamp found in track: {t}")
                    # If there is a previous timestamp, ensure the current one is later.
                    if timestamps and t <= timestamps[-1]:
                        raise GPXValidationError(f"Timestamps not strictly increasing: {t} does not come after {timestamps[-1]}")
                    timestamps.append(t)


def validate_gpx(file_path, strict=False):
    """Run the full validation procedure on the provided GPX file."""
    # Step 1. Parse the file as XML.
    tree = parse_gpx(file_path)
    root = tree.getroot()

    # Step 2. Determine GPX version from the root element.
    version = root.get("version")
    if version not in ("1.0", "1.1"):
        print(f"Unsupported or missing GPX version: {version}")
        sys.exit(1)

    # Step 3. Validate against the corresponding GPX XSD.
    schema = load_schema(version)
    # Note: lenient mode is the default behavior; strict mode is enabled via command-line flag.
    validate_schema(tree, schema, strict=strict, root=root)
    print("XML schema validation passed.")

    # Step 4. GPX-specific content check.
    tracks = root.findall(".//{*}trk")
    if not tracks:
        print("Warning: No tracks found in the GPX file.")

    # Step 5. Timestamp consistency check.
    check_timestamp_consistency(root)
    print("Timestamp consistency check passed.")

    print("GPX file is valid.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Validate a GPX file for XML schema and timestamp consistency.\n"
                    "By default, the validator runs in lenient mode (extra precision is allowed).\n"
                    "Use --strict to enforce strict schema compliance."
    )
    parser.add_argument("gpx_file", help="Path to the GPX file to validate")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode (default is lenient)")

    args = parser.parse_args()
    try:
        validate_gpx(args.gpx_file, strict=args.strict)
    except GPXValidationError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
