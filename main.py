import argparse
import os.path as op

import datetime as dt
import gpxpy
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import pytz

local_tz = pytz.timezone('Europe/Berlin')

from data.race1 import marks
from utils import slug

base_path = '.'

# Define argument parser
parser = argparse.ArgumentParser()
parser.add_argument('files', nargs='+', help='GPX files to process')
parser.add_argument('--start', '-s', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z'), help='Start time (YYYY-MM-DDTHH:MM:SS%z)')
parser.add_argument('--names', '-n', nargs='+', help='Names of the participants')

args = parser.parse_args()

start_time = args.start.replace(tzinfo=pytz.UTC) if args.start else None

tracks = []
points_list = []

# Parse the GPX files
for filename in args.files:
    with open(op.join(base_path, filename), 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    points = [(point.latitude, point.longitude, point.time) for track in gpx.tracks for segment in track.segments for point in segment.points]
    if start_time:
        points = [(lat, lon, time) for (lat, lon, time) in points if time.replace(tzinfo=pytz.UTC) >= start_time]

    points_list.append(points)


title = 'Elbe-Damm Regatta, Race 1'

# Initialize the figure and axis
fig, ax = plt.subplots()
ax.set_title(title)


margin = 0.001  # increase to zoom out
lat_min = min(point[0] for point in [point for points in points_list for point in points]) - margin
lat_max = max(point[0] for point in [point for points in points_list for point in points]) + margin
lon_min = min(point[1] for point in [point for points in points_list for point in points]) - margin
lon_max = max(point[1] for point in [point for points in points_list for point in points]) + margin

ax.set_xlim(lon_min, lon_max)
ax.set_ylim(lat_min, lat_max)

# Initialize the plot with the first data
lines = [ax.plot(points[0][1], points[0][0], '-', label=filename)[0]
         for points, filename in zip(points_list, args.files)]

if args.names:
    for i, name in enumerate(args.names):
        lines[i].set_label(name)

# Add time labels
time_text = ax.text(0.30, 0.95, '', transform=ax.transAxes)

# Static points
if marks:
    for i, (lat, lon) in enumerate(marks, 1):
        ax.plot(lon, lat, marker='o', markersize=5, color='orange')

# Initialize counters
counters = [0] * len(points_list)


# Update function for animation
def update(num, points_list, lines, time_text):
    # Only advance in points_list if their time is less than or equal to the current time
    for points, counter, line in zip(points_list, counters, lines):
        while counter < len(points) and points[counter][2] <= num:
            counter += 1
        # Update lines and time text
        line.set_data([point[1] for point in points[:counter]], [point[0] for point in points[:counter]])
        time_text.set_text('Time: %s' % points[counter-1][2] if counter > 0 else '')
    return [*lines, time_text]


# Get common timeline
# Flatten the list of points from all tracks
flat_points = [point for points in points_list
                      for point in points]
# Extract timestamps
timestamps = [point[2] for point in flat_points]
# Create a sorted set of unique timestamps
timeline = sorted(set(timestamps))

ax.legend(loc='lower right', title="Boats:")

ani = animation.FuncAnimation(fig, update, frames=timeline,
                              fargs=[points_list, lines, time_text],
                              interval=25, blit=True)

# Save the animation as a movie
ani.save(f"{slug(title)}.mp4", fps=10)

plt.show()
