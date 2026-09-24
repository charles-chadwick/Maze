"""Extract an object layer (e.g. "Boundaries") from a group in a Tiled .tmx map,
merge every set of overlapping polygons into a single polygon, and write the
result out as a clean, standalone XML file.

Merged objects:
  * keep the attributes and properties of their source objects
    (the lowest id wins on conflicts) and list every source id in `merged`
  * are re-origined on their top-left corner, so the first point is 0,0
  * get one <hole points="..."/> child per area the merged walls fully enclose
    (Tiled polygons can't have holes; hole points are relative to the object's x,y)

Objects that don't overlap anything are copied unchanged. Merging requires
axis-aligned (rectilinear) polygons or rectangles, which is what maze walls are.

Usage:
    python extract_boundaries.py
    python extract_boundaries.py Maze.tmx --group "Level 2" --layer Boundaries -o Level2_Boundaries.xml
    python extract_boundaries.py --merge-touching   # also merge shapes that only share an edge
"""

import argparse
import copy
import xml.etree.ElementTree as ET
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent
GEOMETRY_ATTRS = {"x", "y", "width", "height"}


def find_layer(root, group_name, layer_name):
    """Return the <objectgroup> named layer_name inside the <group> named group_name."""
    for group in root.iter("group"):
        if group.get("name") != group_name:
            continue
        for layer in group.findall("objectgroup"):
            if layer.get("name") == layer_name:
                return layer
    raise SystemExit(f'No object layer "{layer_name}" found in group "{group_name}".')


def num(value):
    """Parse a number, keeping integers as ints so the output stays clean."""
    f = float(value)
    return int(f) if f.is_integer() else f


def absolute_polygon(obj):
    """Return the object's outline in map coordinates, or None if it isn't mergeable."""
    x, y = num(obj.get("x", 0)), num(obj.get("y", 0))
    if obj.get("rotation", "0") not in ("0", "0.0") or obj.find("ellipse") is not None:
        return None
    polygon = obj.find("polygon")
    if polygon is not None:
        pts = [tuple(num(v) for v in p.split(",")) for p in polygon.get("points").split()]
        pts = [(x + px, y + py) for px, py in pts]
    elif obj.get("width") and obj.get("height") and all(c.tag == "properties" for c in obj):
        w, h = num(obj.get("width")), num(obj.get("height"))
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    else:
        return None
    edges = zip(pts, pts[1:] + pts[:1])
    if not all(a[0] == b[0] or a[1] == b[1] for a, b in edges):
        return None  # not rectilinear
    return pts


def point_in_polygon(px, py, pts):
    inside = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def rasterize(polygons):
    """Split the plane on every polygon edge and return the grid lines plus,
    for each polygon, the set of (col, row) grid cells it covers."""
    xs = sorted({x for pts in polygons for x, _ in pts})
    ys = sorted({y for pts in polygons for _, y in pts})
    covered = []
    for pts in polygons:
        cells = set()
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                if point_in_polygon((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2, pts):
                    cells.add((i, j))
        covered.append(cells)
    return xs, ys, covered


def touches(a, b):
    return any((i + di, j + dj) in b for i, j in a for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def connected_groups(covered, merge_touching):
    """Group polygon indices whose covered cells overlap (or touch, if requested)."""
    parent = list(range(len(covered)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in range(len(covered)):
        for b in range(a + 1, len(covered)):
            if covered[a] & covered[b] or (merge_touching and touches(covered[a], covered[b])):
                parent[find(a)] = find(b)
    groups = {}
    for i in range(len(covered)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def trace_outlines(cells, xs, ys):
    """Trace the boundary of a set of grid cells into closed loops.

    Loops run clockwise on screen (y down), matching Tiled. Outer boundaries
    have positive signed area; holes have negative signed area.
    """
    outgoing = {}
    for i, j in cells:
        corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
        neighbours = [(i, j - 1), (i + 1, j), (i, j + 1), (i - 1, j)]  # top, right, bottom, left
        for k, n in enumerate(neighbours):
            if n not in cells:
                outgoing.setdefault(corners[k], []).append(corners[(k + 1) % 4])

    loops = []
    while outgoing:
        start = min(outgoing, key=lambda p: (p[1], p[0]))
        loop, prev, cur = [start], None, start
        while True:
            options = outgoing[cur]
            if prev is None or len(options) == 1:
                nxt = options[0]
            else:
                # At a pinch point, take the sharpest right turn so loops stay simple.
                dx, dy = cur[0] - prev[0], cur[1] - prev[1]
                nxt = max(options, key=lambda n: dx * (n[1] - cur[1]) - dy * (n[0] - cur[0]))
            options.remove(nxt)
            if not options:
                del outgoing[cur]
            prev, cur = cur, nxt
            if cur == start:
                break
            loop.append(cur)
        # Drop points that sit in the middle of a straight run.
        n = len(loop)
        loop = [p for k, p in enumerate(loop)
                if not (loop[k - 1][0] == p[0] == loop[(k + 1) % n][0]
                        or loop[k - 1][1] == p[1] == loop[(k + 1) % n][1])]
        loops.append([(xs[i], ys[j]) for i, j in loop])
    return loops


def signed_area(pts):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1])) / 2


def points_attr(pts, ox, oy):
    return " ".join(f"{x - ox},{y - oy}" for x, y in pts)


def merge_objects(sources, outline, holes):
    """Build one <object> from several overlapping source objects."""
    sources = sorted(sources, key=lambda o: int(o.get("id")))
    attrs = {}
    for obj in reversed(sources):  # lowest id wins
        attrs.update({k: v for k, v in obj.attrib.items() if k not in GEOMETRY_ATTRS})
    ox, oy = outline[0]
    merged = ET.Element("object", {"id": attrs.pop("id"), "x": str(ox), "y": str(oy), **attrs,
                                   "merged": " ".join(o.get("id") for o in sources)})

    properties = {}
    for obj in reversed(sources):
        for prop in obj.iterfind("properties/property"):
            properties[prop.get("name")] = prop
    if properties:
        props = ET.SubElement(merged, "properties")
        props.extend(copy.deepcopy(p) for _, p in sorted(properties.items()))

    ET.SubElement(merged, "polygon", points=points_attr(outline, ox, oy))
    for hole in holes:
        ET.SubElement(merged, "hole", points=points_attr(hole, ox, oy))
    return merged


def merge_overlapping(objects, merge_touching=False):
    """Return the objects with every overlapping set merged into one, in id order."""
    mergeable = [(obj, pts) for obj in objects if (pts := absolute_polygon(obj))]
    result = [copy.deepcopy(obj) for obj in objects if absolute_polygon(obj) is None]
    if not mergeable:
        return result

    xs, ys, covered = rasterize([pts for _, pts in mergeable])
    for group in connected_groups(covered, merge_touching):
        if len(group) == 1:
            result.append(copy.deepcopy(mergeable[group[0]][0]))
            continue
        loops = trace_outlines(set().union(*(covered[i] for i in group)), xs, ys)
        outlines = [l for l in loops if signed_area(l) > 0]
        holes = [l for l in loops if signed_area(l) < 0]
        sources = [mergeable[i][0] for i in group]
        if len(outlines) != 1:
            raise SystemExit(f"Objects {[o.get('id') for o in sources]} did not merge into one outline.")
        result.append(merge_objects(sources, outlines[0], holes))

    return sorted(result, key=lambda o: int(o.get("id")))


def extract(tmx_path, group_name, layer_name, merge_touching=False):
    root = ET.parse(tmx_path).getroot()
    layer = find_layer(root, group_name, layer_name)
    objects = merge_overlapping(layer.findall("object"), merge_touching)

    out = ET.Element(layer_name.lower(), {
        "source": Path(tmx_path).name,
        "group": group_name,
        "layer": layer_name,
        "tilewidth": root.get("tilewidth", ""),
        "tileheight": root.get("tileheight", ""),
        "count": str(len(objects)),
    })
    # Carry over the layer's own properties (if any), then the objects.
    layer_props = layer.find("properties")
    if layer_props is not None:
        out.append(copy.deepcopy(layer_props))
    out.extend(objects)

    tree = ET.ElementTree(out)
    ET.indent(tree, space="  ")
    return tree


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tmx", nargs="?", default=ASSETS_DIR / "Maze.tmx", help="path to the .tmx map")
    parser.add_argument("--group", default="Level 1", help='group name (default: "Level 1")')
    parser.add_argument("--layer", default="Boundaries", help='object layer name (default: "Boundaries")')
    parser.add_argument("--merge-touching", action="store_true", help="also merge shapes that only share an edge")
    parser.add_argument("-o", "--output", help="output .xml path (default: assets/<Group>_<Layer>.xml)")
    args = parser.parse_args()

    output = args.output or ASSETS_DIR / f"{args.group.replace(' ', '')}_{args.layer}.xml"
    tree = extract(args.tmx, args.group, args.layer, args.merge_touching)
    body = ET.tostring(tree.getroot(), encoding="unicode").replace(" />", "/>")
    Path(output).write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n', encoding="UTF-8")
    print(f"Wrote {tree.getroot().get('count')} objects to {output}")


if __name__ == "__main__":
    main()
