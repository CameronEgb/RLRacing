# states/race_state.py
import pygame
import math
from config import *

def handle_race(game, dt):
    screen = game.screen

    # Input
    keys = pygame.key.get_pressed()
    throttle = (1.0 if keys[pygame.K_w] or keys[pygame.K_UP] else 0.0) - \
               (1.0 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0.0)
    steering = (-1.0 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0.0) + \
               (1.0 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0.0)
    handbrake = keys[pygame.K_SPACE]

    game.player_car.set_input(throttle, steering, handbrake)
    game.player_car.update(dt, game.track_data)

    if game.ai_opponent:
        game.ai_opponent.update(dt)
    game.ai_car.update(dt, game.track_data)

    # Car-car collision
    dx = game.ai_car.x - game.player_car.x
    dy = game.ai_car.y - game.player_car.y
    dist_sq = dx*dx + dy*dy
    if dist_sq < (COLLISION_RADIUS_PLAYER + COLLISION_RADIUS_AI)**2 and dist_sq > 1e-6:
        dist = math.sqrt(dist_sq)
        nx, ny = dx/dist, dy/dist
        overlap = (COLLISION_RADIUS_PLAYER + COLLISION_RADIUS_AI) - dist

        game.player_car.x -= nx * overlap * 0.5
        game.player_car.y -= ny * overlap * 0.5
        game.ai_car.x += nx * overlap * 0.5
        game.ai_car.y += ny * overlap * 0.5

        # Kill normal component of velocity
        vp_n = game.player_car.vx * nx + game.player_car.vy * ny
        va_n = game.ai_car.vx * nx + game.ai_car.vy * ny
        if vp_n > 0:
            game.player_car.vx -= vp_n * nx
            game.player_car.vy -= vp_n * ny
        if va_n < 0:
            game.ai_car.vx -= va_n * nx
            game.ai_car.vy -= va_n * ny

    # Activation after leaving grid
    if not game.player_active:
        dx = game.player_car.x - game.player_spawn[0]
        dy = game.player_car.y - game.player_spawn[1]
        if dx*dx + dy*dy > START_MOVE_RADIUS**2:
            game.player_active = True
    if not game.ai_active:
        dx = game.ai_car.x - game.ai_spawn[0]
        dy = game.ai_car.y - game.ai_spawn[1]
        if dx*dx + dy*dy > START_MOVE_RADIUS**2:
            game.ai_active = True

    # Checkpoint logic
    checkpoints = game.track_data.get("checkpoints", [])
    if checkpoints:
        player_all = ai_all = True
        r2 = CHECKPOINT_RADIUS ** 2
        for cp in checkpoints:
            cx, cy = cp["position"]

            if game.player_active and not cp.get("player_reached", False):
                dx = game.player_car.x - cx
                dy = game.player_car.y - cy
                if dx*dx + dy*dy <= r2:
                    cp["player_reached"] = True
            if game.ai_active and not cp.get("ai_reached", False):
                dx = game.ai_car.x - cx
                dy = game.ai_car.y - cy
                if dx*dx + dy*dy <= r2:
                    cp["ai_reached"] = True

            if not cp.get("player_reached", False):
                player_all = False
            if not cp.get("ai_reached", False):
                ai_all = False

        if player_all or ai_all:
            winner = "PLAYER" if player_all and not ai_all else "AI" if ai_all and not player_all else "TIE"
            game.handle_race_end(winner)

    # Render
    game.game_ux.render()

    # HUD
    if game.arcade.active:
        txt = FONT_HUD.render(f"Arcade → Player: {game.arcade.player_wins}  AI: {game.arcade.ai_wins}", True, (245,245,245))
        rect = txt.get_rect(topright=(SCREEN_WIDTH-20, 20))
        bg = pygame.Surface((rect.width+20, rect.height+10), pygame.SRCALPHA)
        bg.fill((0,0,0,140))
        screen.blit(bg, (SCREEN_WIDTH-rect.width-30, 15))
        screen.blit(txt, rect)

    if game.grand_prix.active:
        txt = FONT_HUD.render(
            f"GP Race {game.grand_prix.race_index + 1}/{GP_RACES_PER_CUP} → Player: {game.grand_prix.player_wins}  AI: {game.grand_prix.ai_wins}",
            True, (245,245,245))
        rect = txt.get_rect(topright=(SCREEN_WIDTH-20, 20))
        bg = pygame.Surface((rect.width+20, rect.height+10), pygame.SRCALPHA)
        bg.fill((0,0,0,140))
        screen.blit(bg, (SCREEN_WIDTH-rect.width-30, 15))
        screen.blit(txt, rect)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                game.state = "menu"
                game.menu_substate = "root"
            if event.key == pygame.K_r:
                game.build_world(game.settings)  # reset race

    pygame.display.flip()
    return True