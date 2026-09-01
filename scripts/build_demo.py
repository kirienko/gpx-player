#!/usr/bin/env python3
"""Build the interactive demo map published at https://kirienko.github.io/gpx-player/.

Run locally with:

    python scripts/build_demo.py --output-dir site
    python -m http.server -d site 8000

The GitHub Pages workflow (.github/workflows/pages.yml) runs the same command on
every push to main, so the published demo always matches the code in the
default branch.
"""
import argparse
from pathlib import Path

from gpx_player.openseamap import create_playback_map

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DATA = REPO_ROOT / "example-data"

TITLE = "Gin Sul Regatta 2024"
DEMO_TRACKS = [
    ("Alex", "osm-demo-Alex.gpx"),
    ("Richard", "osm-demo-Richard.gpx"),
    ("Yury", "osm-demo-Yury.gpx"),
]


def build(output_dir: Path) -> Path:
    """Render the demo tracks into ``output_dir/index.html`` and return its path."""
    names = [name for name, _ in DEMO_TRACKS]
    files = [str(EXAMPLE_DATA / filename) for _, filename in DEMO_TRACKS]

    missing = [f for f in files if not Path(f).is_file()]
    if missing:
        raise SystemExit("missing demo GPX files: " + ", ".join(missing))

    folium_map = create_playback_map(
        files,
        names=names,
        max_speed=12,
        title=TITLE,
        tail_length="normal",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "index.html"
    folium_map.save(str(output))
    return output


def main() -> None:
    """Parse command-line arguments and build the demo site."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output-dir",
        default="site",
        type=Path,
        help="Directory to write index.html into (default: site)",
    )
    args = parser.parse_args()

    output = build(args.output_dir)
    size_kb = output.stat().st_size / 1024
    print(f"Wrote {output} ({size_kb:.0f} KiB)")


if __name__ == "__main__":
    main()
