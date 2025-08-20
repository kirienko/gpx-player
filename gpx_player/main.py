import argparse
import datetime as dt
import os.path as op
from math import atan2, degrees

import gpxpy
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import pytz
from matplotlib.ticker import FuncFormatter, MultipleLocator

from gpx_player.utils import format_func, gen_arrow_head_marker, km_to_nm, slug, timedelta_to_hms

base_path = '.'

# Define argument parser
parser = argparse.ArgumentParser()
parser.add_argument('files', nargs='+', help='GPX files to process')
parser.add_argument('--title', '-t', help='The title of the video')
parser.add_argument('--start', '-s', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z'), help='Start time (YYYY-MM-DDTHH:MM:SS%z)')
parser.add_argument('--end', '-e', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z'), help='End time (YYYY-MM-DDTHH:MM:SS%z)')
parser.add_argument('--race_start', '-r', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z'),
                    help='Race start time (YYYY-MM-DDTHH:MM:SS%z)')
parser.add_argument('--names', '-n', nargs='+', help='Names of the participants')
parser.add_argument('--marks', '-m', help='The file with the static marks to put onto the map. One pair of coordinates per line')
parser.add_argument('--gif', '-g', action='store_true', help='Save as GIF moving picture instead of MP4')
parser.add_argument('--timezone', '-tz', default='Europe/Berlin', help='Timezone to use for processing timestamps')
args = parser.parse_args()
local_tz = pytz.timezone(args.timezone)

start_time = args.start.astimezone(local_tz) if args.start else None
end_time = args.end.astimezone(local_tz) if args.end else None
race_start = args.race_start.astimezone(local_tz) if args.race_start else None

tracks = []
points_list = []

# Parse the GPX files
for filename in args.files:
    with open(op.join(base_path, filename), 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    # all timestamps show the local time from this point on:
    points = [(point.latitude, point.longitude, point.time.astimezone(local_tz)) for track in gpx.tracks for segment in track.segments for
              point in segment.points]
    if start_time:
        points = [(lat, lon, time) for (lat, lon, time) in points if time >= start_time]
    if end_time:
        points = [(lat, lon, time) for (lat, lon, time) in points if time <= end_time]
    points_list.append(points)

title = args.title if args.title else ''

# Initialize the figure and axis
fig, ax = plt.subplots()
ax.set_title(title)
# Apply the custom formatter to the x and y axes
ax.xaxis.set_major_formatter(FuncFormatter(format_func))
ax.yaxis.set_major_formatter(FuncFormatter(format_func))
ax.xaxis.set_major_locator(MultipleLocator(1/120))  # locator at every 1/60/2 degrees = 30"
ax.yaxis.set_major_locator(MultipleLocator(1/360))  # locator at every 1/60/0 degrees = 10"
ax.tick_params(axis='both', labelsize=5)

margin = 0.001  # increase to zoom out
lat_min = min(point[0] for point in [point for points in points_list for point in points]) - margin
lat_max = max(point[0] for point in [point for points in points_list for point in points]) + margin
lon_min = min(point[1] for point in [point for points in points_list for point in points]) - margin
lon_max = max(point[1] for point in [point for points in points_list for point in points]) + margin

ax.set_xlim(lon_min, lon_max)
ax.set_ylim(lat_min, lat_max)

# Initialize the plot with the first data
lines = [ax.plot(points[0][1], points[0][0], '-', linewidth='0.8', label=filename)[0]
         for points, filename in zip(points_list, args.files)]

marker, scale = gen_arrow_head_marker(0)
markersize = 10
heads = [ax.plot(l[0][0], l[0][1], marker=marker, markersize=markersize, color=lines[i].get_color())[0]
            for i, l in enumerate(points_list)]

if args.names:
    for i, name in enumerate(args.names):
        lines[i].set_label(name)
        ax.text(0.7, 0.95 - 0.03*i,
                name[:13]+'...' if len(name) > 13 else f'{name:>13}', transform=ax.transAxes,
                fontsize=6)


# Add time labels
time_text = ax.text(0.30, 0.95, '', transform=ax.transAxes)

# Static points
if args.marks:
    with open(args.marks) as fd:
        marks = [line.strip().split(',') for line in fd.readlines()]
    for i, (lat, lon) in enumerate(marks, 1):
        ax.plot(float(lon), float(lat), marker='o', markersize=5, color='orange')

# Initialize counters in number of input files
counters = [0] * len(points_list)
dist_counter = [0.0] * len(points_list)
speeds = [0.0] * len(points_list)

ax_dist = [ax.text(0.83, 0.95 - 0.03*i, '', fontsize=7, transform=ax.transAxes) for i in range(len(points_list))]
ax_speed = [ax.text(0.93, 0.95 - 0.03*i, '', fontsize=7, transform=ax.transAxes) for i in range(len(points_list))]

# Update function for animation
def update(current_time, points_list, lines, heads, time_text):
    # Only advance in points_list if their time is less than or equal to the current time
    # iterate over points in each file
    for idx, (points, counter, line) in enumerate(zip(points_list, counters, lines)):
        pre_start_counter = 0
        while counter < len(points) and points[counter][2] <= current_time:
            if race_start or start_time:
                if counter > 0 and points[counter][2] >= (race_start or start_time):
                    # Calculate the distance between two consecutive points and add it to dist_counter
                    lat1, lon1, t1 = points[counter-1]
                    lat2, lon2, t2 = points[counter]
                    # gpxpy.geo.haversine_distance returns meters
                    dst = gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2) / 1000  # in km
                    dist_counter[idx] += dst
                    speeds[idx] = km_to_nm(dst)/(t2-t1).total_seconds()*3600
                elif counter > 0 and points[counter][2] < (race_start or start_time):
                    pre_start_counter += 1
            counter += 1
        # Update lines
        if race_start:
            try:
                # `start_counter` = 0 before start
                #                 = counter - 60 after start
                start_counter = 0 if points[counter][2] < race_start \
                                else max(pre_start_counter, counter-60)
            except IndexError:
                start_counter = counter-60
        else:
            start_counter = 0

        line.set_data([point[1] for point in points[start_counter:counter]], [point[0] for point in points[start_counter:counter]])
        # plot the marker
        heads[idx].set_data([points[counter-1][1]], [points[counter-1][0]])
        # Calculate the marker rotation angle
        try:
            y1, x1 = points[counter-2][1], points[counter-2][0]
            y2, x2 = points[counter-1][1], points[counter-1][0]
            theta = degrees(atan2(y2 - y1, x2 - x1))
            marker, scale = gen_arrow_head_marker(90-theta)
            heads[idx].set_marker(marker)
        except IndexError:
            heads[idx].set_marker('o')
        # Update distance/speed table
        ax_dist[idx].set_text(f'{km_to_nm(dist_counter[idx]):.2f} nm')  # Update the displayed distance
        ax_speed[idx].set_text(f'{speeds[idx]:.1f} kt')  # Update the displayed speed
        dist_counter[idx] = 0.

        # Update time text
        if race_start:
            diff_time = current_time - race_start
            minutes = diff_time.total_seconds() / 60
            if minutes < 0:
                time_text.set_text(f"Time to start: {timedelta_to_hms(-diff_time)}")
                time_text.set_color('red')
            else:
                time_text.set_text(f"Time of the race: {timedelta_to_hms(diff_time)}")
                time_text.set_color('black')

        else:
            time_text.set_text(f'Time: {points[counter-1][2]:%Y-%m-%d %H:%M:%S}' if counter > 0 else '')
    return [*lines, *heads, time_text, *ax_dist, *ax_speed]


# Get common timeline
# Flatten the list of points from all tracks
flat_points = [point for points in points_list
                      for point in points]
# Extract timestamps
timestamps = [point[2] for point in flat_points]
# Create a sorted set of unique timestamps
timeline = sorted(set(timestamps))

ax.legend(loc='lower right', fontsize=8)

ani = animation.FuncAnimation(fig, update, frames=timeline, fargs=[points_list, lines, heads, time_text],
                              interval=25, blit=True)

# # Save the animation as a movie
if args.gif:
    ani.save(f"{slug(title or 'untitled')}.gif")
else:
    ani.save(f"{slug(title or 'untitled')}.mp4", fps=10)

plt.show()
