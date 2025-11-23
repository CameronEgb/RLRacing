# states/countdown_state.py
import pygame
import math
from config import *

def handle_countdown(game, dt):
    screen = game.screen

    if game.game_ux:
        game.game_ux.render()
    else:
        screen.fill((20, 40, 60))

    game.countdown_timer -= dt
    if game.countdown_timer <= 0.0:
        game.state = "race"
    else:
        number = str(max(1, int(math.ceil(game.countdown_timer))))
        txt = FONT_COUNTDOWN.render(number, True, (255, 255, 255))
        rect = txt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))

        overlay = pygame.Surface((rect.width + 80, rect.height + 80), pygame.SRCALPHA)
        pygame.draw.ellipse(overlay, (0, 0, 0, 160), overlay.get_rect())
        screen.blit(overlay, overlay.get_rect(center=rect.center))
        screen.blit(txt, rect)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            game.state = "menu"
            game.menu_substate = "root"

    pygame.display.flip()
    return True