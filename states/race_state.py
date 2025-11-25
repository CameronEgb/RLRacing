import pygame
import math
from config import *
from ai.reward_recorder import HumanRewardRecorder  # ← partner’s RL stuff

def handle_race(game, dt):
    screen = game.screen
    mode = game.settings.get("mode", "ARCADE")

    keys = pygame.key.get_pressed()

    # ============================================================
    # 1. INPUTS
    # ============================================================

    if mode == "AI_OPP":
        # -----------------------------
        # PLAYER 1 INPUT (WASD / Arrows)
        # -----------------------------
        throttle = (1.0 if keys[pygame.K_w] or keys[pygame.K_UP] else 0.0) - \
                   (1.0 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0.0)
        steering = (-1.0 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0.0) + \
                   (1.0 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0.0)
        handbrake = keys[pygame.K_SPACE]

        game.player_car.set_input(throttle, steering, handbrake)
        game.player_car.update(dt, game.track_data)

        # AI drives itself
        if game.ai_opponent:
            game.ai_opponent.update(dt, game_ref=game)
        game.ai_car.update(dt, game.track_data)

    else:
        # ============================================================
        # TWO-PLAYER MODE (Arcade + GP)
        # ============================================================

        # ---------- PLAYER 1: WASD ----------
        p1_throttle = (1.0 if keys[pygame.K_w] else 0.0) - (1.0 if keys[pygame.K_s] else 0.0)
        p1_steering = (-1.0 if keys[pygame.K_a] else 0.0) + (1.0 if keys[pygame.K_d] else 0.0)
        p1_handbrake = keys[pygame.K_SPACE]

        game.player_car.set_input(p1_throttle, p1_steering, p1_handbrake)

        # ---------- PLAYER 2: ARROWS ----------
        p2_throttle = (1.0 if keys[pygame.K_UP] else 0.0) - (1.0 if keys[pygame.K_DOWN] else 0.0)
        p2_steering = (-1.0 if keys[pygame.K_LEFT] else 0.0) + (1.0 if keys[pygame.K_RIGHT] else 0.0)
        p2_handbrake = keys[pygame.K_RSHIFT] or keys[pygame.K_RCTRL]

        game.ai_car.set_input(p2_throttle, p2_steering, p2_handbrake)

        game.player_car.update(dt, game.track_data)
        game.ai_car.update(dt, game.track_data)

    # ============================================================
    # 2. COLLISION
    # ============================================================
    dx = game.ai_car.x - game.player_car.x
    dy = game.ai_car.y - game.player_car.y
    dist_sq = dx*dx + dy*dy

    if dist_sq < (COLLISION_RADIUS_PLAYER + COLLISION_RADIUS_AI)**2 and dist_sq > 1e-6:
        dist = math.sqrt(dist_sq)
        nx, ny = dx/dist, dy/dist
        overlap = (COLLISION_RADIUS_PLAYER + COLLISION_RADIUS_AI) - dist

        # Separate cars
        game.player_car.x -= nx * overlap * 0.5
        game.player_car.y -= ny * overlap * 0.5
        game.ai_car.x += nx * overlap * 0.5
        game.ai_car.y += ny * overlap * 0.5

        # Kill normal velocity
        vp_n = game.player_car.vx * nx + game.player_car.vy * ny
        va_n = game.ai_car.vx * nx + game.ai_car.vy * ny

        if vp_n > 0:
            game.player_car.vx -= vp_n * nx
            game.player_car.vy -= vp_n * ny
        if va_n < 0:
            game.ai_car.vx -= va_n * nx
            game.ai_car.vy -= va_n * ny

    # ============================================================
    # 3. LEAVE GRID
    # ============================================================
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

    # ============================================================
    # 4. CHECKPOINTS
    # ============================================================
    checkpoints = game.track_data.get("checkpoints", [])
    if checkpoints:
        p1_all = p2_all = True
        r2 = CHECKPOINT_RADIUS**2

        for cp in checkpoints:
            cx, cy = cp["position"]

            # Player 1
            if game.player_active and not cp.get("player_reached", False):
                dx = game.player_car.x - cx
                dy = game.player_car.y - cy
                if dx*dx + dy*dy <= r2:
                    cp["player_reached"] = True

            # Player 2
            if game.ai_active and not cp.get("ai_reached", False):
                dx = game.ai_car.x - cx
                dy = game.ai_car.y - cy
                if dx*dx + dy*dy <= r2:
                    cp["ai_reached"] = True

            if not cp.get("player_reached", False):
                p1_all = False
            if not cp.get("ai_reached", False):
                p2_all = False

        if p1_all or p2_all:
            winner = "Player 1" if p1_all else "Player 2"
            game.handle_race_end(winner)

    # ============================================================
    # 5. RENDER
    # ============================================================
    game.game_ux.render()

    # ============================================================
    # 6. HUD (MODE-SELECTIVE)
    # ============================================================

    if mode == "ARCADE" and game.arcade.active:
        txt = FONT_HUD.render(
            f"Arcade → P1: {game.arcade.player_wins}  P2: {game.arcade.ai_wins}",
            True, (245,245,245))
        rect = txt.get_rect(topright=(SCREEN_WIDTH-20, 20))
        bg = pygame.Surface((rect.width+20, rect.height+10), pygame.SRCALPHA)
        bg.fill((0,0,0,140))
        screen.blit(bg, (SCREEN_WIDTH-rect.width-30, 15))
        screen.blit(txt, rect)

    elif mode == "GRAND_PRIX" and game.grand_prix.active:
        txt = FONT_HUD.render(
            f"GP Race {game.grand_prix.race_index+1}/{GP_RACES_PER_CUP} → "
            f"P1: {game.grand_prix.player_wins}  P2: {game.grand_prix.ai_wins}",
            True, (245,245,245))
        rect = txt.get_rect(topright=(SCREEN_WIDTH-20, 20))
        bg = pygame.Surface((rect.width+20, rect.height+10), pygame.SRCALPHA)
        bg.fill((0,0,0,140))
        screen.blit(bg, (SCREEN_WIDTH-rect.width-30, 15))
        screen.blit(txt, rect)

    # ============================================================
    # 7. EVENTS
    # ============================================================
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                game.state = "menu"
                game.menu_substate = "root"

            if event.key == pygame.K_r:
                # Always restart race on current settings
                game.start_race(game.settings)

    pygame.display.flip()
    return True
