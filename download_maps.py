import contextily as ctx

# Define bounding box for the area of interest [xmin, ymin, xmax, ymax]


x_min, x_max, y_min, y_max = 9.65, 9.84, 53.54, 53.57
bbox = [x_min, y_min, x_max, y_max]

# Define zoom levels you want (e.g., [12, 13, 14] or just [12])
zoom_levels = [12, 13, 14]

# Directory to save tiles
tile_dir = "./tiles"

# Download the tiles
ctx.tile._fetch_by_bbox(bbox, zoom_levels, path=tile_dir, url=ctx.providers.OpenStreetMap.Mapnik)

# Now set up a custom tile provider using these local tiles
tile_provider = {
    "url": f"file://{tile_dir}/{{z}}/{{x}}/{{y}}.png",
    "min_zoom": min(zoom_levels),
    "max_zoom": max(zoom_levels),
    "attribution": "OpenStreetMap contributors"
}

# Later in your code when plotting:

def get_map(ax):
    ctx.add_basemap(ax, source=tile_provider)
    