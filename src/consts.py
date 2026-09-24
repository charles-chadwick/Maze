from enum import Enum

class ScreenProperties(tuple, Enum):
    BACKGROUND_COLOR = (50, 50, 50)
    FRAME_RATE = (32, 0)
    SCREEN_SIZE = (1920, 1280)