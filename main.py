import pygame
import sys
from track_generator import generate_track
from car import Car
from ux import GameUX
from ai_opponent import AIOpponent


def main():
    pygame.init()

    SCREEN_WIDTH, SCREEN_HEIGHT = 1200, 800
    FPS = 60

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Low-Poly Racing - Chill Vibes")
    clock = pygame.time.Clock()

    # --- State ---
    STATE = "menu"          # "menu" | "race"

    # CURRENT settings actually used for the *live* world
    curr_width = 50
    curr_complexity = 10

    # PENDING settings (edited in menu; only take effect when you press N)
    pend_width = curr_width
    pend_complexity = curr_complexity

    # ---- Helpers ----

    def build_world(width_val: int, complexity_val: int):
        """(Re)build a brand-new world using provided params."""
        track = generate_track(width=width_val, complexity=complexity_val)

        # Start grid from centerline tangent + normal
        c0 = track["centerline"][0]
        c1 = track["centerline"][1]
        tx, ty = (c1[0] - c0[0], c1[1] - c0[1])
        L = (tx * tx + ty * ty) ** 0.5 or 1.0
        tx, ty = tx / L, ty / L
        nx, ny = -ty, tx  # left-hand normal

        # Side-by-side grid inside the lane
        lane_offset = max(10, int(width_val * 0.35))

        # Player on right side of lane
        px = track["start_pos"][0] - nx * lane_offset
        py = track["start_pos"][1] - ny * lane_offset
        player = Car(px, py, track["start_angle"], color=(100, 150, 255), name="Player")

        # AI on left side, slightly back
        ax = track["start_pos"][0] + nx * lane_offset - tx * 20.0
        ay = track["start_pos"][1] + ny * lane_offset - ty * 20.0
        ai = Car(ax, ay, track["start_angle"], color=(255, 150, 100), name="AI Opponent")

        ai_ctrl = AIOpponent(ai, track)
        ux = GameUX(screen, track, player, ai)
        return track, player, ai, ai_ctrl, ux

    def reset_grid_on_current(track, width_val, player, ai, ai_opponent):
        """Reset both cars to the start grid on the *existing* track."""
        c0 = track["centerline"][0]
        c1 = track["centerline"][1]
        tx, ty = (c1[0] - c0[0], c1[1] - c0[1])
        L = (tx * tx + ty * ty) ** 0.5 or 1.0
        tx, ty = tx / L, ty / L
        nx, ny = -ty, tx

        lane_offset = max(10, int(width_val * 0.35))

        px = track["start_pos"][0] - nx * lane_offset
        py = track["start_pos"][1] - ny * lane_offset
        ax = track["start_pos"][0] + nx * lane_offset - tx * 20.0
        ay = track["start_pos"][1] + ny * lane_offset - ty * 20.0

        player.reset(px, py, track["start_angle"])
        ai.reset(ax, ay, track["start_angle"])
        ai_opponent.reset_position(ax, ay, track["start_angle"])  # Sync AI env

    # Build the initial world with current settings
    track, player, ai, ai_opponent, ux = build_world(curr_width, curr_complexity)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if STATE == "menu":
                    if event.key == pygame.K_RETURN:
                        # Start race without changing/regenning the track
                        STATE = "race"
                    elif event.key == pygame.K_n:
                        # Apply PENDING settings and rebuild track
                        nonlocal_curr_width = pend_width
                        nonlocal_curr_complexity = pend_complexity
                        # update outer scope
                        curr_width = nonlocal_curr_width
                        curr_complexity = nonlocal_curr_complexity
                        track, player, ai, ai_opponent, ux = build_world(curr_width, curr_complexity)
                    elif event.key == pygame.K_LEFT:
                        pend_complexity = max(6, pend_complexity - 1)
                    elif event.key == pygame.K_RIGHT:
                        pend_complexity = min(24, pend_complexity + 1)
                    elif event.key == pygame.K_DOWN:
                        pend_width = max(30, pend_width - 2)
                    elif event.key == pygame.K_UP:
                        pend_width = min(80, pend_width + 2)
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()

                elif STATE == "race":
                    if event.key == pygame.K_ESCAPE:
                        # Back to menu (do not exit)
                        STATE = "menu"
                    elif event.key == pygame.K_r:
                        # Reset cars on the EXISTING track (no regen)
                        reset_grid_on_current(track, curr_width, player, ai, ai_opponent)
                    elif event.key == pygame.K_n:
                        # Rebuild using the current PENDING values
                        curr_width = pend_width
                        curr_complexity = pend_complexity
                        track, player, ai, ai_opponent, ux = build_world(curr_width, curr_complexity)

        # --- Update/Render ---
        if STATE == "race":
            keys = pygame.key.get_pressed()
            throttle = (1.0 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0.0) - (
                1.0 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0.0
            )
            steering = (-1.0 if (keys[pygame.K_a] or keys[pygame.K_LEFT]) else 0.0) + (
                1.0 if (keys[pygame.K_d] or keys[pygame.K_RIGHT]) else 0.0
            )
            player.set_input(throttle, steering, keys[pygame.K_SPACE])

            player.update(dt, track)
            ai_opponent.update(dt)
            ai.update(dt, track)

            ux.render()
        else:
            # MENU: draw current world behind a dim overlay and show staged values
            screen.fill((15, 60, 25))
            ux.render()

            overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            font = pygame.font.SysFont("arial", 28)
            small = pygame.font.SysFont("arial", 20)

            lines = [
                "RLRacing — Menu",
                "ENTER: Start   |   N: Apply pending & New Track",
                "ESC: Quit (from menu)   |   R: Reset (in race)",
                "",
                f"Current — Width: {curr_width}   Complexity: {curr_complexity}",
                f"Pending — Width: {pend_width}   Complexity: {pend_complexity}",
                "",
                "Adjust pending with arrow keys:",
                "Up/Down = Width,  Left/Right = Complexity",
            ]

            for i, line in enumerate(lines):
                t = font.render(line, True, (240, 240, 240)) if i < 3 else \
                    small.render(line, True, (230, 230, 230))
                rect = t.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 110 + i * 32))
                screen.blit(t, rect)

        pygame.display.flip()


if __name__ == "__main__":
    main()