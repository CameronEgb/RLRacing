# states/transition_state.py
import pygame
from config import *

def handle_transition(game, dt):
    screen = game.screen

    if game.game_ux:
        game.game_ux.render()
    else:
        screen.fill((20, 40, 60))

    game.transition_timer -= dt

    panel = pygame.Surface((600, 240), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 210))
    rect = panel.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
    screen.blit(panel, rect)

    if game.state == "arcade_transition":
        title = FONT_TITLE.render("Next Race Starting Soon...", True, (245,245,245))
        winner_line = f"Last race: {game.arcade.last_race_winner if hasattr(game.arcade, 'last_race_winner') else '??'} wins!"
        score_line = f"Score → Player: {game.arcade.player_wins}  AI: {game.arcade.ai_wins}"
    else:  # gp_transition
        title = FONT_TITLE.render(f"Race {game.grand_prix.race_index} Complete!", True, (245,245,245))
        winner_line = f"Winner: {game.grand_prix.last_race_winner}"
        score_line = f"Standings → Player: {game.grand_prix.player_wins}  AI: {game.grand_prix.ai_wins}"

    screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, rect.top + 40)))
    screen.blit(FONT_SMALL.render(winner_line, True, (230,230,230)),
                FONT_SMALL.render(winner_line, True, (230,230,230)).get_rect(center=(SCREEN_WIDTH//2, rect.top + 100)))
    screen.blit(FONT_SMALL.render(score_line, True, (230,230,230)),
                FONT_SMALL.render(score_line, True, (230,230,230)).get_rect(center=(SCREEN_WIDTH//2, rect.top + 140)))

    if game.transition_timer <= 0:
        if game.state == "arcade_transition":
            game.state = "menu"
            game.menu_substate = "arcade"
        else:  # gp_transition
            preset = GP_CUPS[game.grand_prix.cup_index][game.grand_prix.race_index]
            settings = {**game.settings, **preset, "mode": "GRAND_PRIX"}
            game.build_world(settings)
            game.countdown_timer = 3.0
            game.state = "arcade_countdown"

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            game.state = "menu"
            game.menu_substate = "root"

    pygame.display.flip()
    return True