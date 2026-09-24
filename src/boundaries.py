from collections.abc import Iterable
import pygame

Coordinate = pygame.Vector2 | tuple[float, float]

class PolygonBoundary:
    def __init__(self, vertices: Iterable[Coordinate]) -> None:
        self.vertices: list[pygame.Vector2] = [pygame.Vector2(vertex) for vertex in vertices]

    def constrain(self, position: Coordinate, hitbox: pygame.Rect) -> pygame.Vector2:
        constrained_position = pygame.Vector2(position)
        hitbox_corners = [pygame.Vector2(corner) for corner in (hitbox.topleft, hitbox.topright, hitbox.bottomleft, hitbox.bottomright)]

        # Repeat because pushing away from one edge can potentially cause another edge to be violated.
        for _ in range(len(self.vertices)):
            position_was_corrected = False

            for edge_start_index, edge_start in enumerate(self.vertices):
                edge_end = self.vertices[(edge_start_index + 1) % len(self.vertices)]

                edge_vector = edge_end - edge_start

                edge_length = edge_vector.length()
                if edge_length == 0:
                    continue

                # Signed distance to the edge from whichever corner pokes furthest past it
                signed_distance_to_edge = min(
                    edge_vector.cross(constrained_position + corner - edge_start) / edge_length
                    for corner in hitbox_corners
                )

                if signed_distance_to_edge < 0:
                    # Push the sprite back inside
                    correction_distance = -signed_distance_to_edge

                    # Perpendicular normal pointing inside. This assumes the polygon is consistently wound.
                    edge_normal = pygame.Vector2(-edge_vector.y, edge_vector.x)
                    edge_normal.normalize_ip()

                    constrained_position += edge_normal * correction_distance
                    position_was_corrected = True

            if not position_was_corrected:
                break

        return constrained_position

    def constrainBox(self, position: Coordinate, box: pygame.Rect, collision_radius: float = 0) -> pygame.Vector2:

        constrained_position = pygame.Vector2(position)
        corners = [pygame.Vector2(corner) for corner in (box.topleft, box.topright, box.bottomleft, box.bottomright)]

        # Repeat because pushing one corner in can push another one out
        for _ in range(len(corners)):
            position_was_corrected = False

            for corner in corners:
                corner_position = constrained_position + corner
                correction = self.constrain(corner_position, collision_radius) - corner_position

                if correction.length_squared() > 0:
                    constrained_position += correction
                    position_was_corrected = True

            if not position_was_corrected:
                break

        return constrained_position

    @staticmethod
    def closestPointOnSegment(query_point: pygame.Vector2, segment_start: pygame.Vector2, segment_end: pygame.Vector2) -> pygame.Vector2:
        segment_vector = segment_end - segment_start

        if segment_vector.length_squared() == 0:
            return segment_start

        projection_fraction = (query_point - segment_start).dot(segment_vector) / segment_vector.length_squared()
        projection_fraction = max(0, min(1, projection_fraction))

        return segment_start + segment_vector * projection_fraction