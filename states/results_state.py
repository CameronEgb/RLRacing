# states/results_state.py
import pygame
from ui.button import Button
from config import *

def handle_results(game, dt):
    screen = game.screen
    mouse = pygame.mouse.get_pos()

    # Draw last race background if available
    if game.game_ux:
        game.game_ux.render()
    else:
        screen.fill((10, 20, 30))

    # Dark overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))

    cx = SCREEN_WIDTH // 2
    y = SCREEN_HEIGHT // 2 - 100

    if game.state == "arcade_results":
        # ---------- ARCADE RESULTS ----------
        title = FONT_TITLE.render("Arcade Session Complete!", True, (245, 245, 245))

        winner = game.arcade.get_final_winner()
        if winner == "PLAYER":
            final_text = "Player 1 wins the Arcade session!"
        elif winner == "AI":
            final_text = "Player 2 wins the Arcade session!"
        else:
            final_text = "The Arcade session ends in a tie!"

        scores = [
            f"Player 1 wins: {game.arcade.player_wins}",
            f"Player 2 wins: {game.arcade.ai_wins}",
        ]

    else:  # gp_results
        # ---------- GRAND PRIX RESULTS ----------
        title = FONT_TITLE.render("Grand Prix Complete!", True, (245, 245, 245))

        cup = CUP_NAMES[game.grand_prix.cup_index]
        winner = game.grand_prix.get_final_winner()
        if winner == "PLAYER":
            final_text = "Player 1 wins the Grand Prix!"
        elif winner == "AI":
            final_text = "Player 2 wins the Grand Prix!"
        else:
            final_text = "The Grand Prix ends in a tie!"

        scores = [
            f"Cup: {cup}",
            f"Player 1 wins: {game.grand_prix.player_wins}",
            f"Player 2 wins: {game.grand_prix.ai_wins}",
        ]

    # Draw title and lines
    screen.blit(title, title.get_rect(center=(cx, y)))
    y += 70
    for line in scores:
        txt = FONT_SMALL.render(line, True, (235, 235, 235))
        screen.blit(txt, txt.get_rect(center=(cx, y)))
        y += 30

    final_surf = FONT_SMALL.render(final_text, True, (245, 245, 200))
    screen.blit(final_surf, final_surf.get_rect(center=(cx, y + 20)))

    # Back button
    back_btn = Button(
        (cx - 140, SCREEN_HEIGHT // 2 + 100, 280, 50),
        "Back to Main Menu",
        FONT_BTN,
        lambda: setattr(game, "state", "menu") or setattr(game, "menu_substate", "root"),
    )
    back_btn.draw(screen, mouse)

    # Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            game.state = "menu"
            game.menu_substate = "root"
        back_btn.handle_event(event)

    pygame.display.flip()
    return True
