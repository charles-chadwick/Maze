from players import Player
import pygame
import sys
from consts import ScreenProperties
from players import Human
from boundaries import Boundaries


# Init the game
pygame.init()
pygame.display.set_caption("Maze Game")

screen = pygame.display.set_mode(ScreenProperties.SCREEN_SIZE)
clock = pygame.time.Clock()
boundaries = Boundaries("Maze")
human = Human("Dumbass", (56, 8), boundaries)  # in the entrance at the top left

# The loop
while True:
    delta_time = clock.tick(ScreenProperties.FRAME_RATE[0]) / 1000 # Tick Away, in seconds since the last frame

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()

    human.update(delta_time)

    screen.fill(ScreenProperties.BACKGROUND_COLOR) # Do up the background
    boundaries.draw(screen)
    screen.blit(human.image, human.rect)

    pygame.display.update() # Update
