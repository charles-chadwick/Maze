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
import xml.etree.ElementTree as ET
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent
RES_DIR = ASSETS_DIR.parent / "src" / "res"
DEFAULT_LAYERS = ["Main Boundary", "Obstacles"]


def num(value):
    """Format a number without a trailing .0 so the output stays clean."""
    value = round(float(value), 4)
    return int(value) if value.is_integer() else value


def absolute_points(obj):
    """Return the object's outline in map coordinates, or None if it isn't a polygon/rectangle."""
    x, y = float(obj.get("x", 0)), float(obj.get("y", 0))
    polygon = obj.find("polygon")
    if polygon is not None:
        return [(x + float(px), y + float(py))
                for px, py in (p.split(",") for p in polygon.get("points").split())]
    if obj.get("width") and obj.get("height") and all(c.tag == "properties" for c in obj):
        w, h = float(obj.get("width")), float(obj.get("height"))
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return None


def clean_points(points, snap):
    """Snap points to the grid, then drop duplicates and points on a straight edge."""
    if snap:
        points = [(round(px / snap) * snap, round(py / snap) * snap) for px, py in points]
    points = [p for i, p in enumerate(points) if p != points[i - 1]]

    def collinear(a, b, c):
        return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-9

    changed = True
    while changed and len(points) > 3:
        changed = False
        for i in range(len(points)):
            if collinear(points[i - 1], points[i], points[(i + 1) % len(points)]):
                del points[i]
                changed = True
                break
    return points


def clean_object(obj, snap):
    points = absolute_points(obj)
    cleaned = copy.deepcopy(obj)
    if points is None:
        return cleaned  # ellipse, point, polyline, text... copy unchanged

    points = clean_points(points, snap)
    ox, oy = points[0]
    for child in cleaned.findall("polygon"):
        cleaned.remove(child)
    cleaned.set("x", str(num(ox)))
    cleaned.set("y", str(num(oy)))
    for attr in ("width", "height"):
        if cleaned.get(attr):
            cleaned.set(attr, str(num(cleaned.get(attr))))
    ET.SubElement(cleaned, "polygon", points=" ".join(f"{num(px - ox)},{num(py - oy)}" for px, py in points))

    slanted = [(a, b) for a, b in zip(points, points[1:] + points[:1]) if a[0] != b[0] and a[1] != b[1]]
    if slanted:
        print(f'  warning: object {obj.get("id")} has {len(slanted)} edge(s) that are not horizontal/vertical')
    return cleaned


def build_layer(layer, snap):
    objects = [clean_object(obj, snap) for obj in layer.findall("object")]
    out = ET.Element("objectgroup", {**layer.attrib, "count": str(len(objects))})
    # Carry over the layer's own properties (if any), then the objects.
    layer_props = layer.find("properties")
    if layer_props is not None:
        out.append(copy.deepcopy(layer_props))
    out.extend(objects)
    return out


def extract(tmx_path, game_name, layer_names, snap):
    """Build one <game> tree with a <level> per Tiled group, holding the chosen object layers."""
    root = ET.parse(tmx_path).getroot()
    if snap is None:
        snap = float(root.get("tilewidth", 0))

    game = ET.Element("game", {
        "name": game_name,
        "source": Path(tmx_path).name,
        "width": str(int(root.get("width")) * int(root.get("tilewidth"))),
        "height": str(int(root.get("height")) * int(root.get("tileheight"))),
        "tilewidth": root.get("tilewidth", ""),
        "tileheight": root.get("tileheight", ""),
    })
    for group in root.iter("group"):
        layers = [l for l in group.findall("objectgroup") if l.get("name") in layer_names]
        if not layers:
            continue
        level = ET.SubElement(game, "level", group.attrib)
        for layer in sorted(layers, key=lambda l: layer_names.index(l.get("name"))):
            level.append(build_layer(layer, snap))

    if not len(game):
        raise SystemExit(f"No levels with layers {layer_names} found in {tmx_path}.")
    tree = ET.ElementTree(game)
    ET.indent(tree, space="  ")
    return tree


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tmx", nargs="?", default=ASSETS_DIR / "Maze.tmx", help="path to the .tmx map")
    parser.add_argument("--name", help="game name, used for the output file (default: the .tmx file name)")
    parser.add_argument("--layer", action="append", dest="layers",
                        help=f"object layer to extract; repeatable (default: {', '.join(DEFAULT_LAYERS)})")
    parser.add_argument("--snap", type=float,
                        help="grid size to snap points to; 0 disables (default: the map's tile width)")
    args = parser.parse_args()

    name = args.name or Path(args.tmx).stem
    tree = extract(args.tmx, name, args.layers or DEFAULT_LAYERS, args.snap)
    RES_DIR.mkdir(parents=True, exist_ok=True)
    output = RES_DIR / f"{name.replace(' ', '')}.xml"
    body = ET.tostring(tree.getroot(), encoding="unicode").replace(" />", "/>")
    output.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n', encoding="UTF-8")
    print(f"Wrote {len(tree.getroot())} level(s) to {output}")


if __name__ == "__main__":
    main()
