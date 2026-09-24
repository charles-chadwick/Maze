from players import Player
import pygame
import sys
from consts import ScreenProperties
from players import Human

# Init the game
pygame.init()
pygame.display.set_caption("Maze Game")

screen = pygame.display.set_mode(ScreenProperties.SCREEN_SIZE)
clock = pygame.time.Clock()
human = Human("Dumbass", (0, 0))

# The loop
while True:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()


    screen.fill(ScreenProperties.BACKGROUND_COLOR) # Do up the background

    pygame.display.update() # Update
    clock.tick(ScreenProperties.FRAME_RATE[0]) / 1000 # Tick Away