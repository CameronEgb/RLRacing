import sys
import random
import math
import pygame

from track_generator import generate_track
from car import Car
from ux import GameUX
from ai_opponent import AIOpponent
from random_ai_opponent import RandomAIOpponent


# Choose which AI controller to use:
#   - RandomAIOpponent: simple baseline, no RL model needed
#   - AIOpponent: RL agent from stable-baselines3
ChosenAIOpponent = RandomAIOpponent
# If you want to switch to the RL agent later, just change to:
# ChosenAIOpponent = AIOpponent


# ---------------------------------------------------------------------------
# Grand Prix cup presets (3 tracks per cup)
# ---------------------------------------------------------------------------

CUP_NAMES = ["Forest Cup", "Canyon Cup", "City Cup"]

GP_CUPS = {
    0: [  # Forest Cup
        {"name": "Forest Ring",   "seed": 1111, "width": 52, "complexity": 9},
        {"name": "Forest Chicane","seed": 1112, "width": 48, "complexity": 12},
        {"name": "Forest Sprint", "seed": 1113, "width": 54, "complexity": 10},
    ],
    1: [  # Canyon Cup
        {"name": "Canyon Loop",   "seed": 2221, "width": 58, "complexity": 11},
        {"name": "Canyon Switch", "seed": 2222, "width": 60, "complexity": 13},
        {"name": "Canyon Run",    "seed": 2223, "width": 56, "complexity": 12},
    ],
    2: [  # City Cup
        {"name": "City Circuit",  "seed": 3331, "width": 46, "complexity": 10},
        {"name": "City Hairpins", "seed": 3332, "width": 44, "complexity": 13},
        {"name": "City Sprint",   "seed": 3333, "width": 48, "complexity": 11},
    ],
}

GP_RACES_PER_CUP = 3


# ---------------------------------------------------------------------------
# Simple button helper
# ---------------------------------------------------------------------------

class Button:
    def __init__(self, rect, label, font, action):
        """
        rect: pygame.Rect or (x, y, w, h)
        label: text on the button
        font: pygame Font
        action: callable to execute when clicked
        """
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.action = action

    def draw(self, surface, mouse_pos):
        hovered = self.rect.collidepoint(mouse_pos)
        base_color = (40, 40, 40)
        hover_color = (70, 70, 70)
        border_color = (220, 220, 220)
        text_color = (240, 240, 240)

        pygame.draw.rect(surface, hover_color if hovered else base_color,
                         self.rect, border_radius=8)
        pygame.draw.rect(surface, border_color, self.rect, width=2,
                         border_radius=8)

        txt = self.font.render(self.label, True, text_color)
        txt_rect = txt.get_rect(center=self.rect.center)
        surface.blit(txt, txt_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.action is not None:
                    self.action()


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------

def main():
    pygame.init()

    SCREEN_WIDTH, SCREEN_HEIGHT = 1200, 800
    FPS = 60

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("RLRacing – RL-ready")
    clock = pygame.time.Clock()

    # ---------------------- High-level state ---------------------------
    # GAME_STATE:
    #   "menu", "arcade_countdown", "race",
    #   "arcade_transition", "arcade_results",
    #   "gp_transition", "gp_results"
    # MENU_STATE:
    #   "root", "arcade", "arcade_track", "grand_prix"
    GAME_STATE = "menu"
    MENU_STATE = "root"

    difficulties = ["EASY", "NORMAL", "HARD"]
    weathers = ["CLEAR", "RAIN", "SNOW"]

    current_settings = {
        "mode": "ARCADE",
        "difficulty": "NORMAL",
        "weather": "CLEAR",
        "track_width": 50,
        "complexity": 10,
        "gp_cup_index": 0,  # 0=Forest, 1=Canyon, 2=City
    }
    pending_settings = current_settings.copy()

    # World objects
    track_data = None
    player_car = None
    ai_car = None
    ai_opponent = None
    game_ux = None

    # Race / checkpoint state
    race_finished = False
    race_winner = None
    CHECKPOINT_RADIUS = 24.0

    # Car–car collision / activation radii
    COLLISION_RADIUS_PLAYER = 15.0
    COLLISION_RADIUS_AI = 15.0
    START_MOVE_RADIUS = 40.0

    player_spawn = (0.0, 0.0)
    ai_spawn = (0.0, 0.0)
    player_active = False
    ai_active = False

    # Arcade session (first to 3 wins)
    arcade_session_active = False
    player_wins = 0
    ai_wins = 0
    ARCADE_WINS_TARGET = 3
    countdown_timer = 0.0
    arcade_transition_timer = 0.0
    arcade_final_winner = None

    # Grand Prix session (3 races per cup)
    gp_session_active = False
    gp_race_index = 0          # 0,1,2 (race number - 1)
    gp_player_wins = 0
    gp_ai_wins = 0
    gp_transition_timer = 0.0
    gp_final_winner = None
    gp_active_cup_index = 0    # which cup is active in this GP session
    gp_last_race_number = 0    # for display in transition

    # ------------------------------------------------------------------
    # Helper: grid calculation (start positions on track)
    # ------------------------------------------------------------------

    def compute_grid_positions(td):
        """
        Compute starting positions for player and AI using the track centerline:
        - Use first two centerline points to get tangent + normal.
        - Place cars on either side of the centerline (side-by-side) on asphalt.
        """
        start = td["start_pos"]
        cx, cy = start
        centerline = td.get("centerline") or []

        if len(centerline) < 2:
            player_pos = (cx, cy)
            ai_pos = (cx - 40, cy)
            return player_pos, ai_pos

        c0 = centerline[0]
        c1 = centerline[1]

        tx = c1[0] - c0[0]
        ty = c1[1] - c0[1]
        L = math.hypot(tx, ty) or 1.0
        tx /= L
        ty /= L

        nx = -ty
        ny = tx

        lane_offset = max(8.0, td.get("width", 50) * 0.22)

        player_pos = (cx - nx * lane_offset, cy - ny * lane_offset)
        ai_pos = (cx + nx * lane_offset, cy + ny * lane_offset)

        return player_pos, ai_pos

    # ------------------------------------------------------------------
    # Helper: build track + cars + UX + AI
    # ------------------------------------------------------------------

    def build_world(settings):
        """
        Build a new track, cars, AI controller, and UX based on the given settings.
        settings may optionally include:
          - "seed": deterministic track
          - "track_name": for HUD/display
        """
        nonlocal track_data, player_car, ai_car, ai_opponent, game_ux
        nonlocal race_finished, race_winner
        nonlocal player_spawn, ai_spawn, player_active, ai_active

        width = settings["track_width"]
        complexity = settings["complexity"]
        seed = settings.get("seed", None)

        # Generate track (deterministic if seed is provided)
        if seed is not None:
            track_data = generate_track(width=width, complexity=complexity, seed=seed)
        else:
            track_data = generate_track(width=width, complexity=complexity)

        # Initialise checkpoint flags
        for cp in track_data.get("checkpoints", []):
            cp["player_reached"] = False
            cp["ai_reached"] = False

        # Starting grid
        player_pos, ai_pos = compute_grid_positions(track_data)

        player_car = Car(
            player_pos[0],
            player_pos[1],
            track_data["start_angle"],
            (100, 150, 255),
            name="Player",
        )
        ai_car = Car(
            ai_pos[0],
            ai_pos[1],
            track_data["start_angle"],
            (255, 150, 100),
            name="AI Opponent",
        )

        player_spawn = (player_car.x, player_car.y)
        ai_spawn = (ai_car.x, ai_car.y)
        player_active = False
        ai_active = False

        # Create AI controller (Random or RL, depending on ChosenAIOpponent)
        ai_opponent = ChosenAIOpponent(ai_car, track_data)

        meta = {
            "mode": settings["mode"],
            "difficulty": settings["difficulty"],
            "weather": settings["weather"],
            "track_width": settings["track_width"],
            "complexity": settings["complexity"],
            "track_name": settings.get("track_name", None),
        }
        game_ux = GameUX(screen, track_data, player_car, ai_car, meta)

        # Apply difficulty / weather if car supports it
        if hasattr(player_car, "set_difficulty"):
            player_car.set_difficulty(settings["difficulty"])
        if hasattr(player_car, "set_weather"):
            player_car.set_weather(settings["weather"])
        if hasattr(ai_car, "set_difficulty"):
            ai_car.set_difficulty(settings["difficulty"])
        if hasattr(ai_car, "set_weather"):
            ai_car.set_weather(settings["weather"])

        race_finished = False
        race_winner = None

    # Helper: build world from current Arcade settings
    def build_arcade_world_from_settings():
        build_world(current_settings)

    # Helper: build a given Grand Prix race (using cup presets)
    def build_gp_world(cup_index, race_index, difficulty, weather):
        preset = GP_CUPS[cup_index][race_index]
        settings = {
            "mode": "GRAND_PRIX",
            "difficulty": difficulty,
            "weather": weather,
            "track_width": preset["width"],
            "complexity": preset["complexity"],
            "gp_cup_index": cup_index,
            "seed": preset["seed"],
            "track_name": preset["name"],
        }
        build_world(settings)

    # Initial world for preview (Arcade default)
    build_arcade_world_from_settings()

    # ------------------------------------------------------------------
    # Fonts and static buttons
    # ------------------------------------------------------------------

    font_title = pygame.font.SysFont("arial", 32, bold=True)
    font_btn = pygame.font.SysFont("arial", 22)
    font_small = pygame.font.SysFont("arial", 18)

    # Results "Back to Mode Select" button (used by Arcade and GP)
    results_button_rect = pygame.Rect(
        SCREEN_WIDTH // 2 - 140, SCREEN_HEIGHT // 2 + 80, 280, 50
    )

    def back_to_mode_select():
        nonlocal GAME_STATE, MENU_STATE
        nonlocal arcade_session_active, player_wins, ai_wins
        nonlocal gp_session_active, gp_player_wins, gp_ai_wins, gp_race_index
        GAME_STATE = "menu"
        MENU_STATE = "root"
        # Reset Arcade session
        arcade_session_active = False
        player_wins = 0
        ai_wins = 0
        # Reset Grand Prix session
        gp_session_active = False
        gp_player_wins = 0
        gp_ai_wins = 0
        gp_race_index = 0

    results_button = Button(
        results_button_rect, "Back to Mode Select", font_btn, back_to_mode_select
    )

    # ------------------------------------------------------------------
    # GP helpers (start / next race)
    # ------------------------------------------------------------------

    def start_gp_session():
        """
        Start a new Grand Prix session from the selected cup/difficulty/weather.
        """
        nonlocal GAME_STATE, current_settings, gp_session_active
        nonlocal gp_race_index, gp_player_wins, gp_ai_wins
        nonlocal countdown_timer, race_finished, race_winner
        nonlocal gp_active_cup_index

        gp_session_active = True
        gp_race_index = 0
        gp_player_wins = 0
        gp_ai_wins = 0

        gp_active_cup_index = pending_settings["gp_cup_index"]

        current_settings["mode"] = "GRAND_PRIX"
        current_settings["difficulty"] = pending_settings["difficulty"]
        current_settings["weather"] = pending_settings["weather"]
        current_settings["gp_cup_index"] = gp_active_cup_index

        build_gp_world(
            gp_active_cup_index,
            gp_race_index,
            current_settings["difficulty"],
            current_settings["weather"],
        )

        race_finished = False
        race_winner = None
        countdown_timer = 3.0
        GAME_STATE = "arcade_countdown"  # general countdown used for both modes

    def start_next_gp_race():
        """
        Advance to the next GP race (assumes gp_race_index already incremented).
        """
        nonlocal GAME_STATE, countdown_timer, race_finished, race_winner

        build_gp_world(
            gp_active_cup_index,
            gp_race_index,
            current_settings["difficulty"],
            current_settings["weather"],
        )

        race_finished = False
        race_winner = None
        countdown_timer = 3.0
        GAME_STATE = "arcade_countdown"

    # ------------------------------------------------------------------
    # Button factories
    # ------------------------------------------------------------------

    def make_root_buttons():
        """
        Root mode-selection menu: only 'Arcade' and 'Grand Prix'.
        """
        center_x = SCREEN_WIDTH // 2
        base_y = SCREEN_HEIGHT // 2 - 40
        btn_w = 260
        btn_h = 48
        gap = 20

        buttons = []

        def go_arcade():
            nonlocal MENU_STATE
            MENU_STATE = "arcade"
            pending_settings["mode"] = "ARCADE"

        def go_gp():
            nonlocal MENU_STATE
            MENU_STATE = "grand_prix"
            pending_settings["mode"] = "GRAND_PRIX"

        buttons.append(
            Button(
                (center_x - btn_w // 2, base_y, btn_w, btn_h),
                "Arcade",
                font_btn,
                go_arcade,
            )
        )
        buttons.append(
            Button(
                (center_x - btn_w // 2, base_y + btn_h + gap, btn_w, btn_h),
                "Grand Prix",
                font_btn,
                go_gp,
            )
        )

        return buttons

    def make_arcade_buttons():
        """
        Arcade menu – difficulty/weather + track preview + apply/start.
        """
        center_x = SCREEN_WIDTH // 2
        base_y = SCREEN_HEIGHT // 2 - 120
        btn_w = 340
        btn_h = 44
        gap = 12

        buttons = []

        def start_arcade_race():
            nonlocal GAME_STATE, arcade_session_active
            nonlocal player_spawn, ai_spawn, player_active, ai_active
            nonlocal race_finished, race_winner, countdown_timer

            # If we are not already in an Arcade session, initialise wins.
            if not arcade_session_active:
                arcade_session_active = True

            # Reset cars to grid for this race on the CURRENT track
            if track_data is not None and player_car is not None and ai_car is not None:
                player_pos, ai_pos = compute_grid_positions(track_data)
                player_car.reset(player_pos[0], player_pos[1], track_data["start_angle"])
                ai_car.reset(ai_pos[0], ai_pos[1], track_data["start_angle"])

                # Reset AI opponent internal state if it supports it
                if ai_opponent is not None and hasattr(ai_opponent, "reset_position"):
                    ai_opponent.reset_position(ai_pos[0], ai_pos[1], track_data["start_angle"])

                # Reset checkpoint flags for both cars on this new race
                for cp in track_data.get("checkpoints", []):
                    cp["player_reached"] = False
                    cp["ai_reached"] = False

                player_spawn = (player_car.x, player_car.y)
                ai_spawn = (ai_car.x, ai_car.y)
                player_active = False
                ai_active = False

            race_finished = False
            race_winner = None

            countdown_timer = 3.0
            GAME_STATE = "arcade_countdown"

        def cycle_difficulty():
            idx = difficulties.index(pending_settings["difficulty"])
            pending_settings["difficulty"] = difficulties[(idx + 1) % len(difficulties)]

        def cycle_weather():
            idx = weathers.index(pending_settings["weather"])
            pending_settings["weather"] = weathers[(idx + 1) % len(weathers)]

        def go_track_menu():
            nonlocal MENU_STATE
            MENU_STATE = "arcade_track"

        def apply_and_preview():
            nonlocal current_settings
            pending_settings["mode"] = "ARCADE"
            current_settings = pending_settings.copy()
            build_arcade_world_from_settings()

        def back_to_root():
            nonlocal MENU_STATE
            MENU_STATE = "root"

        labels_actions = [
            ("Start Arcade Race", start_arcade_race),
            (f"Difficulty: {pending_settings['difficulty']}", cycle_difficulty),
            (f"Weather: {pending_settings['weather']}", cycle_weather),
            ("Track Options…", go_track_menu),
            ("Apply & Preview Track", apply_and_preview),
            ("Back to Mode Select", back_to_root),
        ]

        for i, (label, action) in enumerate(labels_actions):
            x = center_x - btn_w // 2
            y = base_y + i * (btn_h + gap)
            buttons.append(Button((x, y, btn_w, btn_h), label, font_btn, action))

        return buttons

    def make_arcade_track_buttons():
        """
        Track settings sub-menu (width & complexity) used from Arcade.
        """
        center_x = SCREEN_WIDTH // 2
        base_y = SCREEN_HEIGHT // 2 - 40
        btn_w = 260
        btn_h = 40
        gap = 10

        buttons = []

        def width_minus():
            pending_settings["track_width"] = max(30, pending_settings["track_width"] - 2)

        def width_plus():
            pending_settings["track_width"] = min(80, pending_settings["track_width"] + 2)

        def complexity_minus():
            pending_settings["complexity"] = max(6, pending_settings["complexity"] - 1)

        def complexity_plus():
            pending_settings["complexity"] = min(24, pending_settings["complexity"] + 1)

        def apply_and_preview():
            nonlocal current_settings
            pending_settings["mode"] = "ARCADE"
            current_settings = pending_settings.copy()
            build_arcade_world_from_settings()

        def back_to_arcade():
            nonlocal MENU_STATE
            MENU_STATE = "arcade"

        buttons.append(
            Button(
                (center_x - btn_w - 10, base_y, btn_w, btn_h),
                f"Width -  ({pending_settings['track_width']})",
                font_btn,
                width_minus,
            )
        )
        buttons.append(
            Button(
                (center_x + 10, base_y, btn_w, btn_h),
                f"Width +  ({pending_settings['track_width']})",
                font_btn,
                width_plus,
            )
        )

        buttons.append(
            Button(
                (center_x - btn_w - 10, base_y + btn_h + gap, btn_w, btn_h),
                f"Complexity -  ({pending_settings['complexity']})",
                font_btn,
                complexity_minus,
            )
        )
        buttons.append(
            Button(
                (center_x + 10, base_y + btn_h + gap, btn_w, btn_h),
                f"Complexity +  ({pending_settings['complexity']})",
                font_btn,
                complexity_plus,
            )
        )

        buttons.append(
            Button(
                (center_x - btn_w - 10, base_y + 2 * (btn_h + gap) + 10, btn_w, btn_h),
                "Apply & Preview Track",
                font_btn,
                apply_and_preview,
            )
        )
        buttons.append(
            Button(
                (center_x + 10, base_y + 2 * (btn_h + gap) + 10, btn_w, btn_h),
                "Back to Arcade Menu",
                font_btn,
                back_to_arcade,
            )
        )

        return buttons

    def make_gp_buttons():
        """
        Grand Prix menu – 3 cups + difficulty/weather + start/back.
        """
        center_x = SCREEN_WIDTH // 2
        base_y = SCREEN_HEIGHT // 2 - 120
        btn_w = 260
        btn_h = 44
        gap = 10

        buttons = []

        def select_cup(idx):
            def _cb():
                pending_settings["gp_cup_index"] = idx
            return _cb

        def start_gp_race():
            # Kick off a full Grand Prix session (3 races)
            start_gp_session()

        def cycle_difficulty():
            idx = difficulties.index(pending_settings["difficulty"])
            pending_settings["difficulty"] = difficulties[(idx + 1) % len(difficulties)]

        def cycle_weather():
            idx = weathers.index(pending_settings["weather"])
            pending_settings["weather"] = weathers[(idx + 1) % len(weathers)]

        def back_to_root():
            nonlocal MENU_STATE
            MENU_STATE = "root"

        cups = ["Forest Cup", "Canyon Cup", "City Cup"]
        for i, name in enumerate(cups):
            y = base_y + i * (btn_h + gap)
            buttons.append(
                Button(
                    (center_x - btn_w // 2, y, btn_w, btn_h),
                    name,
                    font_btn,
                    select_cup(i),
                )
            )

        y_controls = base_y + 3 * (btn_h + gap) + 10
        buttons.append(
            Button(
                (center_x - btn_w // 2, y_controls, btn_w, btn_h),
                f"Difficulty: {pending_settings['difficulty']}",
                font_btn,
                cycle_difficulty,
            )
        )
        buttons.append(
            Button(
                (center_x - btn_w // 2, y_controls + btn_h + gap, btn_w, btn_h),
                f"Weather: {pending_settings['weather']}",
                font_btn,
                cycle_weather,
            )
        )
        buttons.append(
            Button(
                (center_x - btn_w // 2, y_controls + 2 * (btn_h + gap), btn_w, btn_h),
                "Start Grand Prix",
                font_btn,
                start_gp_race,
            )
        )
        buttons.append(
            Button(
                (center_x - btn_w // 2, y_controls + 3 * (btn_h + gap), btn_w, btn_h),
                "Back to Mode Select",
                font_btn,
                back_to_root,
            )
        )

        return buttons

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # Global ESC handling
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if GAME_STATE in (
                    "race",
                    "arcade_countdown",
                    "arcade_transition",
                    "arcade_results",
                    "gp_transition",
                    "gp_results",
                ):
                    # Abort any session and go back to root menu
                    GAME_STATE = "menu"
                    MENU_STATE = "root"
                    arcade_session_active = False
                    player_wins = 0
                    ai_wins = 0
                    gp_session_active = False
                    gp_player_wins = 0
                    gp_ai_wins = 0
                    gp_race_index = 0
                else:
                    if MENU_STATE == "root":
                        pygame.quit()
                        sys.exit()
                    else:
                        MENU_STATE = "root"

            # ---------------- MENU INPUT ----------------
            if GAME_STATE == "menu":
                if MENU_STATE == "root":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        for btn in make_root_buttons():
                            btn.handle_event(event)

                elif MENU_STATE == "arcade":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        for btn in make_arcade_buttons():
                            btn.handle_event(event)

                elif MENU_STATE == "arcade_track":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        for btn in make_arcade_track_buttons():
                            btn.handle_event(event)

                elif MENU_STATE == "grand_prix":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        for btn in make_gp_buttons():
                            btn.handle_event(event)

            # ---------------- RACE INPUT ----------------
            elif GAME_STATE == "race":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        if track_data and player_car and ai_car:
                            # Reset cars to grid
                            player_pos, ai_pos = compute_grid_positions(track_data)

                            player_car.reset(
                                player_pos[0], player_pos[1], track_data["start_angle"]
                            )
                            ai_car.reset(
                                ai_pos[0], ai_pos[1], track_data["start_angle"]
                            )

                            # Reset AI internal state if supported
                            if ai_opponent is not None and hasattr(ai_opponent, "reset_position"):
                                ai_opponent.reset_position(ai_pos[0], ai_pos[1], track_data["start_angle"])

                            # Reset checkpoint flags
                            for cp in track_data.get("checkpoints", []):
                                cp["player_reached"] = False
                                cp["ai_reached"] = False

                            player_spawn = (player_car.x, player_car.y)
                            ai_spawn = (ai_car.x, ai_car.y)
                            player_active = False
                            ai_active = False

                            race_finished = False
                            race_winner = None

            # ---------------- RESULTS INPUT ------------
            elif GAME_STATE in ("arcade_results", "gp_results"):
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    results_button.handle_event(event)

        # ------------------------------------------------------------------
        # Update & Render based on GAME_STATE
        # ------------------------------------------------------------------

        # ------------------------ COUNTDOWN (Arcade + GP) --------------
        if GAME_STATE == "arcade_countdown":
            if game_ux is not None:
                game_ux.render()
            else:
                screen.fill((20, 40, 60))

            countdown_timer -= dt
            if countdown_timer <= 0.0:
                GAME_STATE = "race"
            else:
                number = str(max(1, int(math.ceil(countdown_timer))))
                txt = pygame.font.SysFont("arial", 80, bold=True).render(
                    number, True, (255, 255, 255)
                )
                rect = txt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                overlay = pygame.Surface(
                    (rect.width + 80, rect.height + 80), pygame.SRCALPHA
                )
                pygame.draw.ellipse(overlay, (0, 0, 0, 160), overlay.get_rect())
                screen.blit(overlay, overlay.get_rect(center=rect.center))
                screen.blit(txt, rect)

            pygame.display.flip()
            continue

        # ------------------------ RACE ----------------------------
        if GAME_STATE == "race":
            if not race_finished:
                keys = pygame.key.get_pressed()
                throttle = (1.0 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0.0) - (
                    1.0 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0.0
                )
                steering = (-1.0 if (keys[pygame.K_a] or keys[pygame.K_LEFT]) else 0.0) + (
                    1.0 if (keys[pygame.K_d] or keys[pygame.K_RIGHT]) else 0.0
                )
                handbrake = keys[pygame.K_SPACE]

                player_car.set_input(throttle, steering, handbrake)
                player_car.update(dt, track_data)

                # AI control
                if ai_opponent is not None:
                    ai_opponent.update(dt)
                ai_car.update(dt, track_data)

                # --- Car–car collision ---
                dx = ai_car.x - player_car.x
                dy = ai_car.y - player_car.y
                dist_sq = dx * dx + dy * dy
                min_dist = COLLISION_RADIUS_PLAYER + COLLISION_RADIUS_AI
                if dist_sq < min_dist * min_dist and dist_sq > 1e-6:
                    dist = math.sqrt(dist_sq)
                    overlap = min_dist - dist
                    nx = dx / dist
                    ny = dy / dist

                    player_car.x -= nx * overlap * 0.5
                    player_car.y -= ny * overlap * 0.5
                    ai_car.x += nx * overlap * 0.5
                    ai_car.y += ny * overlap * 0.5

                    vp_n = player_car.vx * nx + player_car.vy * ny
                    va_n = ai_car.vx * nx + ai_car.vy * ny
                    if vp_n > 0:
                        player_car.vx -= vp_n * nx
                        player_car.vy -= vp_n * ny
                    if va_n < 0:
                        ai_car.vx -= va_n * nx
                        ai_car.vy -= va_n * ny

                # --- Activate cars once they move away from spawn ---
                start_r2 = START_MOVE_RADIUS * START_MOVE_RADIUS
                if not player_active:
                    dx = player_car.x - player_spawn[0]
                    dy = player_car.y - player_spawn[1]
                    if dx * dx + dy * dy > start_r2:
                        player_active = True

                if not ai_active:
                    dx = ai_car.x - ai_spawn[0]
                    dy = ai_car.y - ai_spawn[1]
                    if dx * dx + dy * dy > start_r2:
                        ai_active = True

                # --- Checkpoints / finish lap ---
                checkpoints = track_data.get("checkpoints", [])
                if checkpoints:
                    player_all = True
                    ai_all = True
                    r2 = CHECKPOINT_RADIUS * CHECKPOINT_RADIUS

                    for cp in checkpoints:
                        cx, cy = cp["position"]

                        if player_active and not cp.get("player_reached", False):
                            dx = player_car.x - cx
                            dy = player_car.y - cy
                            if dx * dx + dy * dy <= r2:
                                cp["player_reached"] = True

                        if ai_active and not cp.get("ai_reached", False):
                            dx = ai_car.x - cx
                            dy = ai_car.y - cy
                            if dx * dx + dy * dy <= r2:
                                cp["ai_reached"] = True

                        if not cp.get("player_reached", False):
                            player_all = False
                        if not cp.get("ai_reached", False):
                            ai_all = False

                    # Whoever completes all checkpoints first wins the race
                    if player_all or ai_all:
                        race_finished = True
                        if player_all and not ai_all:
                            race_winner = "PLAYER"
                        elif ai_all and not player_all:
                            race_winner = "AI"
                        else:
                            race_winner = "TIE"
                        print("Race finished! Winner:", race_winner)

            # Render race world
            game_ux.render()

            # Arcade HUD (top-right) showing wins
            if current_settings["mode"] == "ARCADE" and arcade_session_active:
                hud_font = pygame.font.SysFont("arial", 20, bold=True)
                label = hud_font.render(
                    f"Arcade Score  Player: {player_wins}   AI: {ai_wins}",
                    True,
                    (245, 245, 245),
                )
                rect = label.get_rect(topright=(SCREEN_WIDTH - 20, 20))
                bg = pygame.Surface((rect.width + 16, rect.height + 10), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 140))
                bg_rect = bg.get_rect(topright=(SCREEN_WIDTH - 10, 15))
                screen.blit(bg, bg_rect)
                screen.blit(label, rect)

            # Grand Prix HUD (top-right)
            if current_settings["mode"] == "GRAND_PRIX" and gp_session_active:
                hud_font = pygame.font.SysFont("arial", 20, bold=True)
                label = hud_font.render(
                    f"Grand Prix  Race {gp_race_index + 1}/{GP_RACES_PER_CUP}   "
                    f"Player: {gp_player_wins}   AI: {gp_ai_wins}",
                    True,
                    (245, 245, 245),
                )
                rect = label.get_rect(topright=(SCREEN_WIDTH - 20, 20))
                bg = pygame.Surface((rect.width + 16, rect.height + 10), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 140))
                bg_rect = bg.get_rect(topright=(SCREEN_WIDTH - 10, 15))
                screen.blit(bg, bg_rect)
                screen.blit(label, rect)

            pygame.display.flip()

            # Handle end-of-race after drawing
            if race_finished:
                if current_settings["mode"] == "ARCADE" and arcade_session_active:
                    if race_winner == "PLAYER":
                        player_wins += 1
                    elif race_winner == "AI":
                        ai_wins += 1

                    if player_wins >= ARCADE_WINS_TARGET or ai_wins >= ARCADE_WINS_TARGET:
                        arcade_final_winner = (
                            "PLAYER" if player_wins > ai_wins else
                            "AI" if ai_wins > player_wins else
                            "TIE"
                        )
                        arcade_session_active = False
                        GAME_STATE = "arcade_results"
                    else:
                        GAME_STATE = "arcade_transition"
                        arcade_transition_timer = 3.0

                elif current_settings["mode"] == "GRAND_PRIX" and gp_session_active:
                    # Update GP standings
                    gp_last_race_number = gp_race_index + 1
                    if race_winner == "PLAYER":
                        gp_player_wins += 1
                    elif race_winner == "AI":
                        gp_ai_wins += 1

                    gp_race_index += 1

                    if gp_race_index < GP_RACES_PER_CUP:
                        GAME_STATE = "gp_transition"
                        gp_transition_timer = 3.0
                    else:
                        # Grand Prix finished
                        gp_final_winner = (
                            "PLAYER" if gp_player_wins > gp_ai_wins else
                            "AI" if gp_ai_wins > gp_player_wins else
                            "TIE"
                        )
                        gp_session_active = False
                        GAME_STATE = "gp_results"
                else:
                    # Non-session races just kick back to root menu
                    GAME_STATE = "menu"
                    MENU_STATE = "root"

            continue

        # ------------------------ ARCADE TRANSITION ("Next race") ------
        if GAME_STATE == "arcade_transition":
            if game_ux is not None:
                game_ux.render()
            else:
                screen.fill((20, 40, 60))

            arcade_transition_timer -= dt

            panel = pygame.Surface((560, 200), pygame.SRCALPHA)
            panel.fill((0, 0, 0, 210))
            panel_rect = panel.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(panel, panel_rect.topleft)

            title = font_title.render("Time for the next race!", True, (245, 245, 245))
            tr = title.get_rect(center=(SCREEN_WIDTH // 2, panel_rect.top + 40))
            screen.blit(title, tr)

            if race_winner == "PLAYER":
                winner_line = "Last race winner: Player"
            elif race_winner == "AI":
                winner_line = "Last race winner: AI"
            elif race_winner == "TIE":
                winner_line = "Last race ended in a tie"
            else:
                winner_line = "Last race winner: --"

            winner_txt = font_small.render(winner_line, True, (230, 230, 230))
            wr = winner_txt.get_rect(center=(SCREEN_WIDTH // 2, tr.bottom + 25))
            screen.blit(winner_txt, wr)

            score_line = f"Current score – Player: {player_wins}   AI: {ai_wins}"
            score_txt = font_small.render(score_line, True, (230, 230, 230))
            sr = score_txt.get_rect(center=(SCREEN_WIDTH // 2, wr.bottom + 20))
            screen.blit(score_txt, sr)

            msg = font_small.render(
                "You can adjust the track in the Arcade menu before the next race.",
                True,
                (210, 210, 210),
            )
            mr = msg.get_rect(center=(SCREEN_WIDTH // 2, sr.bottom + 20))
            screen.blit(msg, mr)

            if arcade_transition_timer <= 0.0:
                GAME_STATE = "menu"
                MENU_STATE = "arcade"

            pygame.display.flip()
            continue

        # ------------------------ GRAND PRIX TRANSITION ----------------
        if GAME_STATE == "gp_transition":
            if game_ux is not None:
                game_ux.render()
            else:
                screen.fill((20, 40, 60))

            gp_transition_timer -= dt

            panel = pygame.Surface((600, 220), pygame.SRCALPHA)
            panel.fill((0, 0, 0, 210))
            panel_rect = panel.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(panel, panel_rect.topleft)

            title = font_title.render(
                f"Grand Prix – Race {gp_last_race_number} complete!",
                True,
                (245, 245, 245),
            )
            tr = title.get_rect(center=(SCREEN_WIDTH // 2, panel_rect.top + 40))
            screen.blit(title, tr)

            if race_winner == "PLAYER":
                winner_line = "Last race winner: Player"
            elif race_winner == "AI":
                winner_line = "Last race winner: AI"
            elif race_winner == "TIE":
                winner_line = "Last race ended in a tie"
            else:
                winner_line = "Last race winner: --"

            winner_txt = font_small.render(winner_line, True, (230, 230, 230))
            wr = winner_txt.get_rect(center=(SCREEN_WIDTH // 2, tr.bottom + 25))
            screen.blit(winner_txt, wr)

            score_line = f"Current standings – Player: {gp_player_wins}   AI: {gp_ai_wins}"
            score_txt = font_small.render(score_line, True, (230, 230, 230))
            sr = score_txt.get_rect(center=(SCREEN_WIDTH // 2, wr.bottom + 20))
            screen.blit(score_txt, sr)

            msg = font_small.render(
                "Next race will start on a new track in this cup.",
                True,
                (210, 210, 210),
            )
            mr = msg.get_rect(center=(SCREEN_WIDTH // 2, sr.bottom + 20))
            screen.blit(msg, mr)

            if gp_transition_timer <= 0.0:
                # Automatically start the next GP race
                start_next_gp_race()

            pygame.display.flip()
            continue

        # ------------------------ ARCADE RESULTS SCREEN ----------------
        if GAME_STATE == "arcade_results":
            if game_ux is not None:
                game_ux.render()
            else:
                screen.fill((10, 20, 30))

            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))

            title = font_title.render("Arcade Results", True, (245, 245, 245))
            tr = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120))
            screen.blit(title, tr)

            scores_text = [
                f"Player wins: {player_wins}",
                f"AI wins: {ai_wins}",
            ]
            if player_wins > ai_wins:
                winner_text = "Player wins the Arcade session!"
            elif ai_wins > player_wins:
                winner_text = "AI wins the Arcade session!"
            else:
                winner_text = "It's a tie!"

            y = tr.bottom + 20
            for line in scores_text:
                txt = font_small.render(line, True, (235, 235, 235))
                rect = txt.get_rect(center=(SCREEN_WIDTH // 2, y))
                screen.blit(txt, rect)
                y += 26

            txt = font_small.render(winner_text, True, (245, 245, 200))
            rect = txt.get_rect(center=(SCREEN_WIDTH // 2, y + 10))
            screen.blit(txt, rect)

            results_button.draw(screen, mouse_pos)

            pygame.display.flip()
            continue

        # ------------------------ GRAND PRIX RESULTS SCREEN ------------
        if GAME_STATE == "gp_results":
            if game_ux is not None:
                game_ux.render()
            else:
                screen.fill((10, 20, 30))

            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))

            title = font_title.render("Grand Prix Results", True, (245, 245, 245))
            tr = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 140))
            screen.blit(title, tr)

            cup_name = CUP_NAMES[gp_active_cup_index]
            cup_txt = font_small.render(f"Cup: {cup_name}", True, (235, 235, 235))
            cr = cup_txt.get_rect(center=(SCREEN_WIDTH // 2, tr.bottom + 20))
            screen.blit(cup_txt, cr)

            scores_text = [
                f"Player wins: {gp_player_wins}",
                f"AI wins: {gp_ai_wins}",
            ]
            if gp_player_wins > gp_ai_wins:
                winner_text = "Player wins the Grand Prix!"
            elif gp_ai_wins > gp_player_wins:
                winner_text = "AI wins the Grand Prix!"
            else:
                winner_text = "The Grand Prix ends in a tie."

            y = cr.bottom + 20
            for line in scores_text:
                txt = font_small.render(line, True, (235, 235, 235))
                rect = txt.get_rect(center=(SCREEN_WIDTH // 2, y))
                screen.blit(txt, rect)
                y += 26

            txt = font_small.render(winner_text, True, (245, 245, 200))
            rect = txt.get_rect(center=(SCREEN_WIDTH // 2, y + 10))
            screen.blit(txt, rect)

            results_button.draw(screen, mouse_pos)

            pygame.display.flip()
            continue

        # ------------------------ MENU RENDERING -----------------------
        if GAME_STATE == "menu":
            if game_ux is not None:
                game_ux.render()
            else:
                screen.fill((20, 40, 60))

            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))

            if MENU_STATE == "root":
                title = font_title.render("RLRacing – Main Menu", True, (240, 240, 240))
                tr = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 140))
                screen.blit(title, tr)

                subtitle = font_small.render(
                    "Choose a mode to begin:", True, (230, 230, 230)
                )
                sr = subtitle.get_rect(center=(SCREEN_WIDTH // 2, tr.bottom + 20))
                screen.blit(subtitle, sr)

                for btn in make_root_buttons():
                    btn.draw(screen, mouse_pos)

            elif MENU_STATE == "arcade":
                title = font_title.render("Arcade Mode", True, (240, 240, 240))
                tr = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 200))
                screen.blit(title, tr)

                summary = font_small.render(
                    f"Difficulty: {pending_settings['difficulty']}   "
                    f"Weather: {pending_settings['weather']}   "
                    f"Width: {pending_settings['track_width']}   "
                    f"Complexity: {pending_settings['complexity']}",
                    True,
                    (230, 230, 230),
                )
                sr = summary.get_rect(center=(SCREEN_WIDTH // 2, tr.bottom + 15))
                screen.blit(summary, sr)

                hint = font_small.render(
                    "Use these settings to build the next procedural track.",
                    True,
                    (210, 210, 210),
                )
                hr = hint.get_rect(center=(SCREEN_WIDTH // 2, sr.bottom + 18))
                screen.blit(hint, hr)

                for btn in make_arcade_buttons():
                    btn.draw(screen, mouse_pos)

            elif MENU_STATE == "arcade_track":
                panel = pygame.Surface((720, 360), pygame.SRCALPHA)
                panel.fill((0, 0, 0, 190))
                panel_rect = panel.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                screen.blit(panel, panel_rect.topleft)

                title = font_title.render("Arcade – Track Settings", True, (240, 240, 240))
                tr = title.get_rect(center=(SCREEN_WIDTH // 2, panel_rect.top + 40))
                screen.blit(title, tr)

                info_lines = [
                    "Adjust width and complexity for future Arcade tracks.",
                    f"Current width: {pending_settings['track_width']}",
                    f"Current complexity: {pending_settings['complexity']}",
                ]
                y = tr.bottom + 10
                for line in info_lines:
                    txt = font_small.render(line, True, (230, 230, 230))
                    rect = txt.get_rect(center=(SCREEN_WIDTH // 2, y))
                    screen.blit(txt, rect)
                    y += 22

                for btn in make_arcade_track_buttons():
                    btn.draw(screen, mouse_pos)

            elif MENU_STATE == "grand_prix":
                title = font_title.render("Grand Prix", True, (240, 240, 240))
                tr = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 220))
                screen.blit(title, tr)

                summary = font_small.render(
                    f"Select a cup. Difficulty: {pending_settings['difficulty']}   "
                    f"Weather: {pending_settings['weather']}",
                    True,
                    (230, 230, 230),
                )
                sr = summary.get_rect(center=(SCREEN_WIDTH // 2, tr.bottom + 15))
                screen.blit(summary, sr)

                cups = make_gp_buttons()
                cup_index = pending_settings["gp_cup_index"]

                # First 3 buttons are cups
                for i in range(3):
                    btn = cups[i]
                    if i == cup_index:
                        highlight_rect = btn.rect.inflate(8, 8)
                        pygame.draw.rect(
                            screen, (80, 80, 40), highlight_rect, border_radius=10
                        )
                    btn.draw(screen, mouse_pos)

                # Remaining buttons are difficulty/weather/start/back
                for btn in cups[3:]:
                    btn.draw(screen, mouse_pos)

            pygame.display.flip()


if __name__ == "__main__":
    main()
