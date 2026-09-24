import pygame
import sys
from consts import ScreenProperties

# Init the game
pygame.init()
pygame.display.set_caption("Nice Game")

screen = pygame.display.set_mode(ScreenProperties.SCREEN_SIZE)
clock = pygame.time.Clock()

# The loop
while True:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()


    screen.fill(ScreenProperties.BACKGROUND_COLOR) # Do up the background

    pygame.display.update() # Update
    clock.tick(FRAME_RATE) / 1000 # Tick Away