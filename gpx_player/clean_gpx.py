import argparse
import sys

from gpx_player.validator import validate_gpx, GPXValidationError
from gpx_player.gpx_utils import remove_extensions_tags


def clean_gpx_file(gpx_file: str, overwrite: bool = False) -> tuple[str, int]:
    """Validate and clean up a GPX file.

    The file is first validated using :func:`validator.validate_gpx`. If the
    validation succeeds, all ``<extensions>`` blocks are removed using
    :func:`gpx_utils.remove_extensions_tags`.

    Parameters
    ----------
    gpx_file : str
        Path to the GPX file.

    overwrite : bool, optional
        If ``True`` the input file will be modified in place instead of
        creating a new file. Default is ``False``.

    Returns
    -------
    tuple[str, int]
        The path to the cleaned file and the number of removed blocks.
    """
    # Validate the file; this will raise GPXValidationError on failure
    validate_gpx(gpx_file, strict=True)
    return remove_extensions_tags(gpx_file, overwrite=overwrite)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and clean a GPX file")
    parser.add_argument("gpx_file", help="Path to the GPX file to clean")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the original GPX file instead of creating a copy",
    )
    args = parser.parse_args()

    try:
        cleaned, removed = clean_gpx_file(args.gpx_file, overwrite=args.overwrite)
    except GPXValidationError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.overwrite:
        print(f"Removed {removed} <extensions> blocks. Overwrote {cleaned}")
    else:
        print(f"Removed {removed} <extensions> blocks. Saved cleaned file to {cleaned}")


if __name__ == "__main__":
    main()
