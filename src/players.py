from abc import ABC
import pygame
from pygame.sprite import Sprite
from pygame.sprite import Group
from boundaries import Boundaries
from consts import PlayerAction, PlayerDirection, PlayerState, PlayerType, ScreenProperties


class Player(Sprite, ABC):

    DIRECTION_VECTORS = {
        PlayerDirection.LEFT: pygame.Vector2(-1, 0),
        PlayerDirection.RIGHT: pygame.Vector2(1, 0),
        PlayerDirection.UP: pygame.Vector2(0, -1),
        PlayerDirection.DOWN: pygame.Vector2(0, 1),
    }

    @property
    def action(self) -> PlayerAction:
        return self._action

    @action.setter
    def action(self, value: PlayerAction) -> None:
        self._action = value

    @property
    def direction(self) -> PlayerDirection:
        return self._direction

    @direction.setter
    def direction(self, value: PlayerDirection) -> None:
        self._direction = value

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value.strip()

    @property
    def position(self) -> tuple:
        return tuple(self.rect.topleft)

    @position.setter
    def position(self, value: tuple):
        self.rect.topleft = value

    @property
    def type(self) -> PlayerType:
        return self._type

    @type.setter
    def type(self, value: PlayerType):
        self._type = value

    def __init__(self, player_type: PlayerType, name: str, position: tuple, boundaries: Boundaries,
                 speed: float, color: tuple, *groups: Group):
        super().__init__(*groups)
        self.action = PlayerAction.STAND
        self.direction = PlayerDirection.DOWN
        self.name = name
        self.type = player_type
        self.boundaries = boundaries
        self.speed = speed  # pixels per second

        self.image = pygame.Surface(ScreenProperties.PLAYER_SIZE)
        self.image.fill(color)
        # FRect keeps fractional positions, so slow movement doesn't stall or stutter.
        self.rect = pygame.FRect(position, ScreenProperties.PLAYER_SIZE)

        if not self.boundaries.allowsRect(self.rect):
            raise ValueError(f"{self.name} can't start at {position}: it's outside the boundary or inside an obstacle")

    def move(self, directions: list[PlayerDirection], dt: float) -> None:
        """Walk in the given directions for dt seconds; the boundaries stop the player at walls."""
        velocity = sum((self.DIRECTION_VECTORS[direction] for direction in directions), pygame.Vector2())

        if velocity.length_squared() == 0:
            self.action = PlayerAction.STAND
            return

        self.action = PlayerAction.WALK
        self.direction = directions[-1]
        velocity.scale_to_length(self.speed * dt)  # diagonals are no faster than straight lines

        # Every position change goes through the boundaries, which keeps the player inside at all times.
        self.rect = self.boundaries.move(self.rect, velocity.x, velocity.y)


class Human(Player):

    SPEED = 160
    COLOR = (230, 200, 60)
    CONTROLS = {
        PlayerDirection.LEFT: (pygame.K_LEFT, pygame.K_a),
        PlayerDirection.RIGHT: (pygame.K_RIGHT, pygame.K_d),
        PlayerDirection.UP: (pygame.K_UP, pygame.K_w),
        PlayerDirection.DOWN: (pygame.K_DOWN, pygame.K_s),
    }

    def __init__(self, name: str, position: tuple, boundaries: Boundaries, *groups: Group):
        super().__init__(PlayerType.HUMAN, name, position, boundaries, self.SPEED, self.COLOR, *groups)

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.move([direction for direction, key_codes in self.CONTROLS.items() if any(keys[key] for key in key_codes)], dt)
