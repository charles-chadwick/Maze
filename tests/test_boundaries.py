import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pygame

from boundaries import Boundaries, PolygonBoundary, Walls

# A 100x100 room with a 20x20 obstacle in the middle.
ROOM = [(0, 0), (100, 0), (100, 100), (0, 100)]
OBSTACLE = [(40, 40), (60, 40), (60, 60), (40, 60)]


def level(*polygons: PolygonBoundary) -> Walls:
    walls = Walls()
    for polygon in polygons:
        walls.extend(polygon.walls)
    return walls


class WallsMoveTest(unittest.TestCase):

    def setUp(self):
        self.room = PolygonBoundary(ROOM)
        self.obstacle = PolygonBoundary(OBSTACLE, keep_inside=False)
        self.walls = level(self.room, self.obstacle)

    def test_free_movement_is_unchanged(self):
        moved = self.walls.move(pygame.FRect(10, 10, 10, 10), 5.5, 3.25)
        self.assertEqual(moved.topleft, (15.5, 13.25))

    def test_stops_flush_against_room_walls(self):
        rect = pygame.FRect(10, 10, 10, 10)
        self.assertEqual(self.walls.move(rect, 500, 0).right, 100)
        self.assertEqual(self.walls.move(rect, -500, 0).left, 0)
        self.assertEqual(self.walls.move(rect, 0, 500).bottom, 100)
        self.assertEqual(self.walls.move(rect, 0, -500).top, 0)

    def test_cannot_skip_through_an_obstacle(self):
        rect = pygame.FRect(10, 45, 10, 10)
        self.assertEqual(self.walls.move(rect, 500, 0).right, 40)
        rect = pygame.FRect(45, 10, 10, 10)
        self.assertEqual(self.walls.move(rect, 0, 500).bottom, 40)

    def test_stops_against_far_side_of_obstacle(self):
        rect = pygame.FRect(80, 45, 10, 10)
        self.assertEqual(self.walls.move(rect, -500, 0).left, 60)

    def test_slides_along_a_wall_when_moving_diagonally(self):
        moved = self.walls.move(pygame.FRect(90, 10, 10, 10), 5, 5)
        self.assertEqual(moved.topleft, (90, 15))

    def test_passes_a_wall_it_is_exactly_level_with(self):
        # Top edge exactly level with the obstacle's bottom: it should slide underneath.
        moved = self.walls.move(pygame.FRect(10, 60, 10, 10), 60, 0)
        self.assertEqual(moved.left, 70)

    def test_winding_does_not_matter(self):
        walls = level(PolygonBoundary(ROOM[::-1]), PolygonBoundary(OBSTACLE[::-1], keep_inside=False))
        self.assertEqual(walls.move(pygame.FRect(10, 45, 10, 10), 500, 0).right, 40)
        self.assertEqual(walls.move(pygame.FRect(10, 10, 10, 10), 0, -500).top, 0)


class ConcaveBoundaryTest(unittest.TestCase):
    """The shape of Level 1's main boundary: a big room with an entrance notch in the top left."""

    def setUp(self):
        self.boundary = PolygonBoundary([(32, 0), (32, 1248), (1888, 1248), (1888, 32), (96, 32), (96, 0)])

    def test_point_deep_inside_is_not_moved(self):
        rect = pygame.FRect(500, 500, 16, 16)
        self.assertEqual(self.boundary.move(rect, 0, 0).topleft, (500, 500))
        self.assertEqual(self.boundary.move(rect, 100, 0).topleft, (600, 500))

    def test_entrance_notch_edges_only_block_inside_the_notch(self):
        in_notch = pygame.FRect(40, 5, 16, 16)
        self.assertEqual(self.boundary.move(in_notch, 500, 0).right, 96)
        self.assertEqual(self.boundary.move(in_notch, 0, -500).top, 0)

        below_notch = pygame.FRect(40, 100, 16, 16)
        self.assertEqual(self.boundary.move(below_notch, 500, 0).left, 540)
        self.assertEqual(self.boundary.move(below_notch, 0, -500).top, 0)  # lined up with the notch

        beside_notch = pygame.FRect(200, 100, 16, 16)
        self.assertEqual(self.boundary.move(beside_notch, 0, -500).top, 32)

    def test_can_walk_out_of_the_notch_into_the_room(self):
        moved = self.boundary.move(pygame.FRect(40, 5, 16, 16), 0, 100)
        self.assertEqual(moved.top, 105)

    def test_rejects_slanted_edges(self):
        with self.assertRaises(ValueError):
            PolygonBoundary([(0, 0), (10, 5), (0, 10)])


class AllowsRectTest(unittest.TestCase):

    def setUp(self):
        self.room = PolygonBoundary(ROOM)
        self.obstacle = PolygonBoundary(OBSTACLE, keep_inside=False)

    def test_room(self):
        self.assertTrue(self.room.allowsRect(pygame.FRect(10, 10, 10, 10)))
        self.assertTrue(self.room.allowsRect(pygame.FRect(0, 0, 10, 10)))
        self.assertFalse(self.room.allowsRect(pygame.FRect(95, 10, 10, 10)))
        self.assertFalse(self.room.allowsRect(pygame.FRect(200, 10, 10, 10)))

    def test_obstacle(self):
        self.assertTrue(self.obstacle.allowsRect(pygame.FRect(10, 10, 10, 10)))
        self.assertTrue(self.obstacle.allowsRect(pygame.FRect(30, 40, 10, 10)))
        self.assertFalse(self.obstacle.allowsRect(pygame.FRect(35, 45, 10, 10)))
        self.assertFalse(self.obstacle.allowsRect(pygame.FRect(45, 45, 10, 10)))


class GameXmlTest(unittest.TestCase):

    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.boundaries = Boundaries("Maze")

    def test_obstacles_keep_rects_outside(self):
        for boundary in self.boundaries.boundaries["Obstacles"]:
            self.assertFalse(boundary.keep_inside)

    def test_moves_through_level_1(self):
        # Start in the entrance notch and walk straight down the left-hand corridor to the bottom wall.
        rect = pygame.FRect(40, 4, 16, 16)
        self.assertTrue(self.boundaries.allowsRect(rect))
        self.assertEqual(self.boundaries.move(rect, 0, 5000).bottom, 1248)

        # Between the first two columns of obstacles: down is stopped by the long bar at y=608,
        # left by the first obstacle's right side.
        rect = pygame.FRect(300, 150, 16, 16)
        self.assertTrue(self.boundaries.allowsRect(rect))
        self.assertEqual(self.boundaries.move(rect, 0, 5000).bottom, 608)
        self.assertEqual(self.boundaries.move(rect, -500, 0).left, 288)

    def test_obstacle_blocks_movement(self):
        rect = pygame.FRect(100, 50, 16, 16)
        self.assertEqual(self.boundaries.move(rect, 0, 500).bottom, 96)


if __name__ == "__main__":
    unittest.main()
