# gpx-player
## GPX Race Visualizer

GPX Race Visualizer is a Python script to visualize the progression of multiple GPS tracks (e.g., from a race) on a 2D map. 
It takes as input one or more GPX files and creates an animation showing the movement of each track over time. 
This is a simple, open-source alternative to features like Strava's Flyby, which require an account and can have privacy issues.

### Modes
The player supports two modes:
#### 1. "Video" mode
Produce an `MP4` or a `GIF` file showing how the situation developed.
For sailing races, it also calculates the distance covered after the 'start' signal and the current speed.
##### Example:
![Example output](example.gif "Example of the script output")

#### 2. Map mode
Displays the track on OpenSeaMap.
You can see the full tracks with colour-coded speeds,
and you can 'play' the tracks and see the markers move around the map. While playing, a legend shows each boat's distance travelled (in nautical miles), current speed (in knots), and average speed in knots.

#### Example:
Since GitHub Markdown doesn't allow embedding HTML, 
you can see an [interactive example](https://kirienko.github.io/static/GinSul-2024.html) here.

Screenshot:
[![OPS Example](./example_osm.png)](https://kirienko.github.io/static/GinSul-2024.html)
## Installation

Install directly from PyPI using pip:
```bash
pip install gpx-player
```

Alternatively, clone the repository and install the required dependencies manually:
```bash
git clone https://github.com/kirienko/gpx-player.git
cd gpx-player
pip install -r requirements.txt
```

## Usage
To run the script producing `mp4`, pass one or more GPX file paths as command-line arguments:
```bash
python main.py example-data/track1.gpx example-data/track2.gpx
```
To get a sea map, run the `openseamap.py`:
```bash
python openseamap.py --title 'Gin Sul Regatta 2024' --names Alex Yury Richard \
     --files example-data/osm-demo-Alex.gpx example-data/osm-demo-Richard.gpx \
             example-data/osm-demo-Yury.gpx
```

A more sophisticated example, that produced a video above:
```bash
python main.py example-data/track1.gpx example-data/track2.gpx example-data/track3.gpx \
       --start 2023-07-01T10:53:00+0000 \
       --names "Mr. Pommeroy" "Miss Sophie" "Sir Toby²" \
       --title "Elbe-Damm Regatta (01.07.2023), Race 1" \
       --race_start 2023-07-01T10:58:00+0000 --marks example-data/marks.txt -g
```
### Additional parameters:
* `--title` or `-t`: The title of the video
* `--start` or `-s`: start time in the format `2023-06-30T12:53:00+0200`, all points _before_ that will not be plotted
* `--end` or `-e`: end time in the format `2023-06-30T13:53:00+0200`, all points _after_ that will not be plotted
* `--names` or `-n`: names of the participants (otherwise the file names will be used in the legend)
* `--race_start`, `-r`: Race start time in the format `YYYY-MM-DDTHH:MM:SS%z`, e.g. `2023-07-01T12:29:00+0200`
* `--names` or `-n`: Names of the participants
* `--marks`or`-m`: The file with the static marks to put onto the map. One pair of coordinates per line, see below.
* `--gif` or `-g`: Save as GIF moving picture instead of MP4
* `--timezone` or `-tz`: Local timezone to use for processing timestamps, e.g. `America/Los_Angeles`, see [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (default: `Europe/Berlin`).

## Marks
The script also supports visualizing predefined marks on the map, which can be useful for events like sailing regattas.
The marks are defined as a list of (latitude, longitude) tuples in a separate text file and can be added to the script as follows:
```
53.542484632728, 9.801163896918299
53.542997846049374, 9.80611324310303
53.54823800356785, 9.812614917755129
53.54921647691311, 9.807373881340029
53.54508251196638, 9.80433225631714
```

## Getting GPX Files

GPX files can be obtained from several GPS-tracking services:
* Strava: Go to the activity page and click on the wrench icon. Then select "Export GPX".
* Garmin Connect: Open the activity, go to the gear icon and select "Export to GPX".
* Endomondo: From the workout page, click the three-dot menu icon and select "Export". Then choose "GPX".

## GPX Validation

For the `gpx-player` to work properly, it needs the correct GPX files.
You can verify that you are inputting the correct file by using the special validator 
included in this package.

The `validator.py` script is a command-line utility and module for validating GPX files. 
It checks for XML schema conformance and timestamp consistency, 
supporting both strict and lenient modes. 
Errors are raised as `GPXValidationError` which can be caught in Python code. 
To run as a CLI tool, use:
```bash
python validator.py path/to/yourfile.gpx --strict
```

The `--strict` parameter is optional. In most cases you do not need it, 
because files that strictly correspond to the GPX schema are rare. 
For example, almost all modern files contain coordinates, elevations and time stamps 
with more decimal places than originally planned.

Also, to better understand your GPX file, you can use the `gpxinfo` console command 
that comes with `gpxpy`. If you are already using the player, you have it:

```bash
$ gpxinfo example-data/osm_track1.gpx 
File: example-data/osm_track1.gpx
    Waypoints: 0
    Routes: 0
    Length 2D: 9.621km
    Length 3D: 9.648km
    Moving time: 01:05:22
    Stopped time: n/a
    Max speed: 3.12m/s = 11.22km/h
    Avg speed: 2.46m/s = 8.85km/h
    Total uphill: 97.20m
    Total downhill: 98.40m
    Started: 2024-07-24 15:59:05+00:00
    Ended: 2024-07-24 17:04:27+00:00
    Points: 776
    Avg distance between points: 12.40m

```

## GPX Cleanup

For convenience, the repository provides `clean_gpx.py`. This utility first
validates a GPX file using `validator.py` and then removes all `<extensions>`
blocks using :func:`remove_extensions_tags` from `gpx_utils`. By default the
cleaned file is saved alongside the original with `_noext` appended to its name.
If the optional `--overwrite` flag is used, the original file is modified in
place.

Run it from the command line as follows:

```bash
python clean_gpx.py path/to/yourfile.gpx [--overwrite]
```

If validation fails, the command exits with an error message. The output reports
how many extension blocks were removed.

## Support
Now you can buy me a coffee to encourage further development!

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/kirienko)
