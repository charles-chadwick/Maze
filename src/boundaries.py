import os.path

import pygame
from xml.etree import ElementTree
from collections.abc import Iterable
from consts import Paths, ScreenProperties

Coordinate = pygame.Vector2 | tuple[float, float]


class Walls:
    """Axis-aligned wall segments, grouped by the direction of movement each one blocks.

    Vertical walls are stored as (x, y_start, y_end) and horizontal walls as (y, x_start, x_end).
    """

    def __init__(self) -> None:
        self.left: list[tuple[float, float, float]] = []  # stop movement to the left
        self.right: list[tuple[float, float, float]] = []  # stop movement to the right
        self.top: list[tuple[float, float, float]] = []  # stop movement up
        self.bottom: list[tuple[float, float, float]] = []  # stop movement down

    def crosses(self, rectangle: pygame.FRect) -> bool:
        """True if any wall passes through the inside of rectangle."""
        return any(
            rectangle.left < x < rectangle.right and start < rectangle.bottom and end > rectangle.top
            for x, start, end in self.left + self.right
        ) or any(
            rectangle.top < y < rectangle.bottom and start < rectangle.right and end > rectangle.left
            for y, start, end in self.top + self.bottom
        )

    def extend(self, other: "Walls") -> None:
        self.left += other.left
        self.right += other.right
        self.top += other.top
        self.bottom += other.bottom

    def move(self, rectangle: pygame.FRect, delta_x: float, delta_y: float) -> pygame.FRect:
        """Return rectangle moved by (delta_x, delta_y), stopped flush against the first wall in its way.

        Each axis is swept separately (x, then y), so a rectangle can't skip through a wall however
        far it moves in one step, and moving diagonally into a wall slides along it.
        """
        rectangle = rectangle.copy()

        # Only walls that overlap the rectangle's span on the other axis can block it. The comparisons
        # are strict, so a rectangle exactly level with the end of a wall slides past it.
        if delta_x > 0:
            blocking_walls = [x for x, start, end in self.right
                              if x >= rectangle.right and start < rectangle.bottom and end > rectangle.top]
            rectangle.right = min([rectangle.right + delta_x, *blocking_walls])
        elif delta_x < 0:
            blocking_walls = [x for x, start, end in self.left
                              if x <= rectangle.left and start < rectangle.bottom and end > rectangle.top]
            rectangle.left = max([rectangle.left + delta_x, *blocking_walls])

        if delta_y > 0:
            blocking_walls = [y for y, start, end in self.bottom
                              if y >= rectangle.bottom and start < rectangle.right and end > rectangle.left]
            rectangle.bottom = min([rectangle.bottom + delta_y, *blocking_walls])
        elif delta_y < 0:
            blocking_walls = [y for y, start, end in self.top
                              if y <= rectangle.top and start < rectangle.right and end > rectangle.left]
            rectangle.top = max([rectangle.top + delta_y, *blocking_walls])

        return rectangle


class PolygonBoundary:
    """A polygon a rectangle must stay inside (keep_inside=True) or outside (an obstacle).

    Every edge must be horizontal or vertical.
    """

    def __init__(self, vertices: Iterable[Coordinate], keep_inside: bool = True) -> None:
        self.vertices: list[pygame.Vector2] = [pygame.Vector2(vertex) for vertex in vertices]
        self.keep_inside = keep_inside

        # Tiled polygons can be drawn either way round; make them clockwise (on screen, y down).
        if self.signedArea() < 0:
            self.vertices.reverse()

        # Walking a clockwise polygon, its inside is always on the right. For an obstacle the
        # allowed side is the outside, so walk each edge backwards to put that on the right instead.
        # Then which way an edge runs says which side of the allowed area it is on.
        self.walls = Walls()
        for index, start in enumerate(self.vertices):
            end = self.vertices[(index + 1) % len(self.vertices)]
            if not keep_inside:
                start, end = end, start

            if start.x == end.x and start.y != end.y:
                wall = (start.x, min(start.y, end.y), max(start.y, end.y))
                (self.walls.right if end.y > start.y else self.walls.left).append(wall)
            elif start.y == end.y and start.x != end.x:
                wall = (start.y, min(start.x, end.x), max(start.x, end.x))
                (self.walls.top if end.x > start.x else self.walls.bottom).append(wall)
            elif start != end:
                raise ValueError(f"Edge {tuple(start)} -> {tuple(end)} is not horizontal or vertical")

    def allowsRectangle(self, rectangle: pygame.FRect) -> bool:
        """True if rectangle is entirely on the allowed side (e.g. to check a spawn position)."""
        return not self.walls.crosses(rectangle) and self.isInside(rectangle.center) == self.keep_inside

    def isInside(self, point: Coordinate) -> bool:
        point_x, point_y = point
        inside = False
        for index, start in enumerate(self.vertices):
            end = self.vertices[(index + 1) % len(self.vertices)]
            if (start.y > point_y) != (end.y > point_y):
                crossing_x = start.x + (point_y - start.y) * (end.x - start.x) / (end.y - start.y)
                if point_x < crossing_x:
                    inside = not inside
        return inside

    def move(self, rectangle: pygame.FRect, delta_x: float, delta_y: float) -> pygame.FRect:
        return self.walls.move(rectangle, delta_x, delta_y)

    def signedArea(self) -> float:
        return sum(
            vertex.cross(self.vertices[(index + 1) % len(self.vertices)])
            for index, vertex in enumerate(self.vertices)
        ) / 2


class BoundaryObject(PolygonBoundary):
    """One <object> from the game XML: its Tiled attributes plus its polygon in map coordinates."""

    OBSTACLE_TYPE = "Obstacle"

    def __init__(self, object_id: int, name: str, object_type: str, x: float, y: float,
                 points: Iterable[Coordinate]) -> None:
        self.id = object_id
        self.name = name
        self.type = object_type
        self.x = x
        self.y = y
        self.points: list[pygame.Vector2] = [pygame.Vector2(point) for point in points]  # relative to x, y

        # Tiled stores points relative to the object's x, y; movement needs them in map coordinates.
        super().__init__((pygame.Vector2(x, y) + point for point in self.points),
                         keep_inside=object_type != self.OBSTACLE_TYPE)

    @classmethod
    def fromXml(cls, xml_object: ElementTree.Element) -> "BoundaryObject":
        xml_polygon = xml_object.find("polygon")
        points = [tuple(float(value) for value in point.split(",")) for point in xml_polygon.get("points").split()]

        return cls(
            object_id=int(xml_object.get("id")),
            name=xml_object.get("name"),
            object_type=xml_object.get("type"),
            x=float(xml_object.get("x")),
            y=float(xml_object.get("y")),
            points=points,
        )

    def __repr__(self) -> str:
        return f"BoundaryObject(id={self.id}, name={self.name!r}, type={self.type!r}, x={self.x}, y={self.y}, points={len(self.points)})"


class Boundaries:

    def __init__(self, game_name):

        xml_path = os.path.join(Paths.RES_PATH, f"{game_name}.xml")

        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"{xml_path} does not exist!")

        self.boundaries: dict[str, list[BoundaryObject]] = {}
        self.walls = Walls()

        xml_game = ElementTree.parse(xml_path).getroot()
        if xml_game.get("name") != game_name:
            raise ValueError(f"{xml_path} is for game '{xml_game.get('name')}', not '{game_name}'")

        for xml_level in xml_game.findall("level[@name='Level 1']/objectgroup"):
            object_group = str(xml_level.get("name"))
            self.boundaries[object_group] = [
                BoundaryObject.fromXml(xml_object) for xml_object in xml_level.findall("object")
            ]
            for boundary in self.boundaries[object_group]:
                self.walls.extend(boundary.walls)

    def allowsRectangle(self, rectangle: pygame.FRect) -> bool:
        return all(boundary.allowsRectangle(rectangle) for group in self.boundaries.values() for boundary in group)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the outline of every boundary and obstacle."""
        for group in self.boundaries.values():
            for boundary in group:
                color = ScreenProperties.BOUNDARY_COLOR if boundary.keep_inside else ScreenProperties.OBSTACLE_COLOR
                pygame.draw.polygon(surface, color, boundary.vertices, 2)

    def move(self, rectangle: pygame.FRect, delta_x: float, delta_y: float) -> pygame.FRect:
        """Move rectangle by (delta_x, delta_y), keeping it inside every boundary and outside every obstacle."""
        return self.walls.move(rectangle, delta_x, delta_y)
