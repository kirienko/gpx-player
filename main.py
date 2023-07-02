import os.path as op

import gpxpy
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import pytz

local_tz = pytz.timezone('Europe/Berlin')

from data.race3 import marks
from utils import slug

base_path = './data'
# Parse the GPX files
with open(op.join(base_path, 'Elbe-Damm-race3-Yury.gpx'), 'r') as gpx_file:
    gpx1 = gpxpy.parse(gpx_file)

with open(op.join(base_path, 'Segeln-MSC-Damm-Regatta-run3-Sirtoby.gpx'), 'r') as gpx_file:
    gpx2 = gpxpy.parse(gpx_file)

title = 'Elbe-Damm Regatta, Race 3'

# Extract track points and timestamps
points1 = [(point.latitude, point.longitude, point.time) for track in gpx1.tracks for segment in track.segments for point in segment.points]
points2 = [(point.latitude, point.longitude, point.time) for track in gpx2.tracks for segment in track.segments for point in segment.points]

# Initialize the figure and axis
fig, ax = plt.subplots()
ax.set_title(title)


margin = 0.001  # increase to zoom out
lat_min = min(point[0] for point in points1 + points2) - margin
lat_max = max(point[0] for point in points1 + points2) + margin
lon_min = min(point[1] for point in points1 + points2) - margin
lon_max = max(point[1] for point in points1 + points2) + margin

ax.set_xlim(lon_min, lon_max)
ax.set_ylim(lat_min, lat_max)

# Initialize the plot with the first data
line1, = ax.plot(points1[0][1], points1[0][0], 'r-', label="Miss Sophie")
line2, = ax.plot(points2[0][1], points2[0][0], 'b-', label="Sir Toby²")

# Add time labels
time_text = ax.text(0.30, 0.95, '', transform=ax.transAxes)

# Static points
if marks:
    for i, (lat, lon) in enumerate(marks, 1):
        ax.plot(lon, lat, marker='o', markersize=5, color='orange')

# Initialize counters for points1 and points2
counter1 = counter2 = 0


# Update function for animation
def update(num, points1, points2, line1, line2, time_text):
    global counter1, counter2

    # Only advance in points1 or points2 if their time is less than or equal to the current time
    while counter1 < len(points1) and points1[counter1][2] <= num:
        counter1 += 1
    while counter2 < len(points2) and points2[counter2][2] <= num:
        counter2 += 1

    # Update lines and time text
    line1.set_data([point[1] for point in points1[:counter1]], [point[0] for point in points1[:counter1]])
    line2.set_data([point[1] for point in points2[:counter2]], [point[0] for point in points2[:counter2]])
    # timestamp = points1[counter1-1][2] if counter1 > 0 else None
    timestamp = points1[counter1-1][2] if counter1 > 0 else points2[counter2-1][2]
    formatted_time = timestamp.replace(tzinfo=pytz.utc).astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S')
    time_text.set_text('Time: %s' % formatted_time)
    return [line1, line2, time_text]


# Get common timeline
timeline = sorted(set([point[2] for point in points1 + points2]))

ax.legend(loc='lower right', title="Boats:")

ani = animation.FuncAnimation(fig, update, frames=timeline,
                              fargs=[points1, points2, line1, line2, time_text],
                              interval=25, blit=True)

# Save the animation as a movie
ani.save(f"{slug(title)}.mp4", fps=10)

plt.show()
