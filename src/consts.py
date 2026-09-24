from enum import Enum, StrEnum
import os.path

class Paths(StrEnum):
    RES_PATH = os.path.join(os.path.dirname(__file__), "res")

class PlayerAction(StrEnum):
    STAND = "stand"
    WALK = "walk"
    ATTACK = "attack"

class PlayerDirection(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"

class PlayerState(StrEnum):
    ALIVE = "alive"
    WOUNDED = "wounded"
    DEAD = "dead"

class PlayerType(StrEnum):
    HUMAN = "Human"

class ScreenProperties(tuple, Enum):
    BACKGROUND_COLOR = (50, 50, 50)
    CELL_SIZE = (32, 32)
    FRAME_RATE = (32, 0)
    PLAYER_SIZE = (16, 16)
    SCREEN_SIZE = (1920, 1280)