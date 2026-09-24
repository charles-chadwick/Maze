"""Extract object layers (e.g. "Main Boundary" and "Obstacles") from every level
(Tiled group) in a .tmx map and write them to one clean XML file, src/res/<Game>.xml:

    <game name="Maze" ...>
      <level id="2" name="Level 1">
        <objectgroup id="3" name="Main Boundary" ...> <object .../> </objectgroup>
        <objectgroup id="4" name="Obstacles" ...> <object .../> ... </objectgroup>
      </level>
    </game>

Every object keeps all of its attributes and properties. Its shape is cleaned up:
  * rectangles get an explicit <polygon>, so every object is parsed the same way
  * points are snapped to a grid (the map's tile size by default) to remove
    the float noise Tiled leaves behind when polygons are drawn by hand
  * duplicate points and points in the middle of a straight edge are dropped
  * the object's x,y is moved to its first point, so points start at 0,0

Usage:
    python extract_boundaries.py
    python extract_boundaries.py Maze.tmx --name Maze --layer "Main Boundary" --layer Obstacles
    python extract_boundaries.py --snap 1   # snap to whole pixels instead of the tile grid
    python extract_boundaries.py --snap 0   # keep points exactly as drawn
"""

import argparse
import copy
from xml.etree import ElementTree
from pathlib import Path

ASSETS_DIRECTORY = Path(__file__).resolve().parent
RESOURCES_DIRECTORY = ASSETS_DIRECTORY.parent / "src" / "res"
DEFAULT_LAYERS = ["Main Boundary", "Obstacles"]


def format_number(value):
    """Format a number without a trailing .0 so the output stays clean."""
    value = round(float(value), 4)
    return int(value) if value.is_integer() else value


def absolute_points(tiled_object):
    """Return the object's outline in map coordinates, or None if it isn't a polygon/rectangle."""
    x, y = float(tiled_object.get("x", 0)), float(tiled_object.get("y", 0))
    polygon = tiled_object.find("polygon")
    if polygon is not None:
        return [(x + float(point_x), y + float(point_y))
                for point_x, point_y in (point.split(",") for point in polygon.get("points").split())]
    is_rectangle = all(child.tag == "properties" for child in tiled_object)
    if tiled_object.get("width") and tiled_object.get("height") and is_rectangle:
        width, height = float(tiled_object.get("width")), float(tiled_object.get("height"))
        return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    return None


def clean_points(points, snap):
    """Snap points to the grid, then drop duplicates and points on a straight edge."""
    if snap:
        points = [(round(point_x / snap) * snap, round(point_y / snap) * snap) for point_x, point_y in points]
    points = [point for index, point in enumerate(points) if point != points[index - 1]]

    def collinear(previous_point, point, next_point):
        return abs((point[0] - previous_point[0]) * (next_point[1] - previous_point[1])
                   - (point[1] - previous_point[1]) * (next_point[0] - previous_point[0])) < 1e-9

    changed = True
    while changed and len(points) > 3:
        changed = False
        for index in range(len(points)):
            if collinear(points[index - 1], points[index], points[(index + 1) % len(points)]):
                del points[index]
                changed = True
                break
    return points


def clean_object(tiled_object, snap):
    points = absolute_points(tiled_object)
    cleaned = copy.deepcopy(tiled_object)
    if points is None:
        return cleaned  # ellipse, point, polyline, text... copy unchanged

    points = clean_points(points, snap)
    origin_x, origin_y = points[0]
    for child in cleaned.findall("polygon"):
        cleaned.remove(child)
    cleaned.set("x", str(format_number(origin_x)))
    cleaned.set("y", str(format_number(origin_y)))
    for attribute in ("width", "height"):
        if cleaned.get(attribute):
            cleaned.set(attribute, str(format_number(cleaned.get(attribute))))
    ElementTree.SubElement(cleaned, "polygon", points=" ".join(
        f"{format_number(point_x - origin_x)},{format_number(point_y - origin_y)}" for point_x, point_y in points))

    slanted = [(start, end) for start, end in zip(points, points[1:] + points[:1])
               if start[0] != end[0] and start[1] != end[1]]
    if slanted:
        print(f'  warning: object {tiled_object.get("id")} has {len(slanted)} edge(s) that are not horizontal/vertical')
    return cleaned


def build_layer(layer, snap):
    objects = [clean_object(tiled_object, snap) for tiled_object in layer.findall("object")]
    object_group = ElementTree.Element("objectgroup", {**layer.attrib, "count": str(len(objects))})
    # Carry over the layer's own properties (if any), then the objects.
    layer_properties = layer.find("properties")
    if layer_properties is not None:
        object_group.append(copy.deepcopy(layer_properties))
    object_group.extend(objects)
    return object_group


def extract(tmx_path, game_name, layer_names, snap):
    """Build one <game> tree with a <level> per Tiled group, holding the chosen object layers."""
    root = ElementTree.parse(tmx_path).getroot()
    if snap is None:
        snap = float(root.get("tilewidth", 0))

    game = ElementTree.Element("game", {
        "name": game_name,
        "source": Path(tmx_path).name,
        "width": str(int(root.get("width")) * int(root.get("tilewidth"))),
        "height": str(int(root.get("height")) * int(root.get("tileheight"))),
        "tilewidth": root.get("tilewidth", ""),
        "tileheight": root.get("tileheight", ""),
    })
    for group in root.iter("group"):
        layers = [layer for layer in group.findall("objectgroup") if layer.get("name") in layer_names]
        if not layers:
            continue
        level = ElementTree.SubElement(game, "level", group.attrib)
        for layer in sorted(layers, key=lambda layer: layer_names.index(layer.get("name"))):
            level.append(build_layer(layer, snap))

    if not len(game):
        raise SystemExit(f"No levels with layers {layer_names} found in {tmx_path}.")
    tree = ElementTree.ElementTree(game)
    ElementTree.indent(tree, space="  ")
    return tree


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tmx", nargs="?", default=ASSETS_DIRECTORY / "Maze.tmx", help="path to the .tmx map")
    parser.add_argument("--name", help="game name, used for the output file (default: the .tmx file name)")
    parser.add_argument("--layer", action="append", dest="layers",
                        help=f"object layer to extract; repeatable (default: {', '.join(DEFAULT_LAYERS)})")
    parser.add_argument("--snap", type=float,
                        help="grid size to snap points to; 0 disables (default: the map's tile width)")
    arguments = parser.parse_args()

    name = arguments.name or Path(arguments.tmx).stem
    tree = extract(arguments.tmx, name, arguments.layers or DEFAULT_LAYERS, arguments.snap)
    RESOURCES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output = RESOURCES_DIRECTORY / f"{name.replace(' ', '')}.xml"
    body = ElementTree.tostring(tree.getroot(), encoding="unicode").replace(" />", "/>")
    output.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n', encoding="UTF-8")
    print(f"Wrote {len(tree.getroot())} level(s) to {output}")


if __name__ == "__main__":
    main()
