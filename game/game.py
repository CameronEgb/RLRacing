import pygame
import math
import os
from config import *
from .track_generator import generate_track
from .track_storer import load_track
from .car import Car
from ui.ux import GameUX

# Agents
from ai.agents.random_ai_opponent import RandomAIOpponent
from ai.agents.rl_opponent import RLAIOpponent

from utils import compute_grid_positions
from modes.arcade_mode import ArcadeSession
from modes.grand_prix_mode import GrandPrixSession
from modes.ai_opp_mode import AIOppSession


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("RLRacing – AI Battle Ready")
        self.clock = pygame.time.Clock()
        self.running = True

        self.state = "menu"
        self.menu_substate = "root"

        self.settings = {
            "mode": "ARCADE",
            "difficulty": "NORMAL",
            "weather": "CLEAR",
            "track_width": 50,
            "complexity": 10,
            "gp_cup_index": 0,
            "track_filename": None,
        }
        self.pending = self.settings.copy()

        # --- INITIALIZE MENU BACKGROUND ---
        # Generate a dummy track so the menu has something to render
        self.track_data = generate_track(50, 10, seed=555)

        # Initialize dummy cars for the menu view
        start_pos = self.track_data["start_pos"]
        start_angle = self.track_data["start_angle"]

        self.player_car = Car(
            start_pos[0],
            start_pos[1],
            start_angle,
            (0, 120, 255),
            name="Player",
        )
        self.ai_car = Car(
            start_pos[0] - 50,
            start_pos[1],
            start_angle,
            (200, 0, 0),
            name="AI",
        )

        # Setup Initial UX for Menu Background
        self.game_ux = GameUX(
            self.screen,
            self.track_data,
            self.player_car,
            self.ai_car,
            {"mode": "MENU"},
        )
        # Center camera on start for menu
        self.game_ux.camera_offset = (
            start_pos[0] - SCREEN_WIDTH // 2,
            start_pos[1] - SCREEN_HEIGHT // 2,
        )

        self.ai_opponent = None
        self.player_spawn = self.ai_spawn = (0, 0)
        self.player_active = self.ai_active = False

        # Sessions
        self.arcade = ArcadeSession()
        self.grand_prix = GrandPrixSession()
        self.ai_opp = AIOppSession()

        self.transition_timer = 0.0

    def build_world(self, settings=None):
        self.start_race(settings)
    # ------------------------------------------------------------------
    # Preview track for menu background (no race start)
    # ------------------------------------------------------------------
    def preview_track(self, settings=None):
        """
        Rebuilds track, cars, and UX for menu preview using the given settings
        (or self.pending). Does NOT start a race or change self.state.
        """
        if settings is None:
            settings = self.pending.copy()

        mode = settings.get("mode", "ARCADE")
        weather = settings.get("weather", "CLEAR")

        # 1. Determine track data (preview only)
        if mode == "GRAND_PRIX":
            cup_index = settings.get("gp_cup_index", 0)
            cup = GP_CUPS[cup_index]
            # Preview the first race of the selected cup
            t_conf = cup[0]
            self.track_data = generate_track(
                t_conf["width"],
                t_conf["complexity"],
                t_conf["seed"],
            )
            # Tie track weather to menu choice for preview
            self.track_data["intended_weather"] = weather

        elif mode == "AI_OPP":
            # For now, don't auto-load a specific AI track for preview.
            # Just keep whatever is already displayed.
            return

        else:  # ARCADE or default
            self.track_data = generate_track(
                settings["track_width"],
                settings["complexity"],
                seed=None,
            )
            # Tie track weather to menu choice for preview
            self.track_data["intended_weather"] = weather

        # 2. Setup cars for preview
        start_angle = self.track_data["start_angle"]
        p_pos, a_pos = compute_grid_positions(self.track_data)
        preview_weather = self.track_data.get("intended_weather", weather)

        # Names depend on mode
        if mode == "AI_OPP":
            name_p1 = "Player"
            name_p2 = "AI Opponent"
        else:
            name_p1 = "Player 1"
            name_p2 = "Player 2"

        self.player_car = Car(
            p_pos[0], p_pos[1], start_angle,
            (0, 120, 255),
            name=name_p1,
            weather=preview_weather
        )

        self.ai_car = Car(
            a_pos[0], a_pos[1], start_angle,
            (200, 0, 0),
            name=name_p2,
            weather=preview_weather
        )

        # 3. UX metadata for preview
        meta = {
            "mode": "MENU_PREVIEW",
            "track_name": "Preview Track",
            "weather": preview_weather,
        }
        self.game_ux = GameUX(
            self.screen,
            self.track_data,
            self.player_car,
            self.ai_car,
            meta,
        )

    # ------------------------------------------------------------------
    # Start a race based on current settings
    # ------------------------------------------------------------------
    def start_race(self, settings=None):
        """
        Initializes a race based on current pending settings.
        """
        # Apply settings
        if not settings:
            self.settings = self.pending.copy()
        else:
            self.settings = settings

        mode = self.settings["mode"]

        # 1. Determine Track Data
        if mode == "AI_OPP":
            # Load specific track from file
            fname = self.settings.get("track_filename")
            if fname:
                self.ai_opp.start(fname)
                loaded = load_track(self.ai_opp.track_file)
                if loaded:
                    self.track_data = loaded
                else:
                    print("Error loading track, falling back to generated.")
                    self.track_data = generate_track(50, 10, seed=999)
            else:
                self.track_data = generate_track(50, 10, seed=999)

        elif mode == "GRAND_PRIX":
            cup = GP_CUPS[self.settings["gp_cup_index"]]
            idx = self.grand_prix.race_index
            t_conf = cup[idx]
            self.track_data = generate_track(
                t_conf["width"], t_conf["complexity"], t_conf["seed"]
            )
            # ALWAYS sync track weather to menu-selected GP weather
            self.track_data["intended_weather"] = self.settings.get("weather", "CLEAR")

            if not self.grand_prix.active:
                self.grand_prix.start(
                    self.settings["gp_cup_index"],
                    self.settings["difficulty"],
                    self.settings["weather"],
                )


        else:  # ARCADE
            if self.track_data is None:
                self.track_data = generate_track(
                    self.settings["track_width"],
                    self.settings["complexity"],
                    seed=None,  # Random fallback
                )
            # Sync track weather to the chosen Arcade weather
            self.track_data["intended_weather"] = self.settings.get("weather", "CLEAR")
            if not self.arcade.active:
                self.arcade.start()

        # 2. Setup Cars
        start_angle = self.track_data["start_angle"]
        p_pos, a_pos = compute_grid_positions(self.track_data)

        # Use track weather as source of truth for the race
        weather_for_race = self.track_data.get(
            "intended_weather", self.settings.get("weather", "CLEAR")
        )

        if mode == "AI_OPP":
            name_p1 = "Player"
            name_p2 = "AI Opponent"
        else:
            name_p1 = "Player 1"
            name_p2 = "Player 2"

        self.player_car = Car(
            p_pos[0], p_pos[1], start_angle,
            (0, 120, 255),
            name=name_p1,
            weather=weather_for_race
        )

        self.ai_car = Car(
            a_pos[0], a_pos[1], start_angle,
            (200, 0, 0),
            name=name_p2,
            weather=weather_for_race
        )

        # 3. Setup AI Agent
        if mode == "AI_OPP":
            if self.ai_opp.model_path:
                # Pass obs_type to RL opponent
                self.ai_opponent = RLAIOpponent(
                    self.ai_car,
                    self.ai_opp.model_path,
                    obs_type=self.ai_opp.obs_type,
                )
            else:
                print(
                    "No model found, placeholding with Random AI fallback agent."
                )
                self.ai_opponent = RandomAIOpponent(self.ai_car, self.track_data)
                self.ai_opponent.set_difficulty(1, 1)
        else:
            self.ai_opponent = RandomAIOpponent(self.ai_car, self.track_data)
            self.ai_opponent.set_difficulty(1, 1)

        # 4. Setup UX
        meta = {
            "mode": mode,
            "track_name": (
                self.ai_opp.track_name if mode == "AI_OPP" else "Procedural Track"
            ),
            "weather": weather_for_race,
        }
        self.game_ux = GameUX(
            self.screen,
            self.track_data,
            self.player_car,
            self.ai_car,
            meta,
        )

        # 5. Finalize
        self.player_spawn = p_pos
        self.ai_spawn = a_pos
        self.player_active = self.ai_active = False
        self.state = "race"

    def run(self):
        from states import get_state_handler

        self.running = True
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            handler = get_state_handler(self)
            if handler(self, dt) is False:
                self.running = False

            # Event loop for quit
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

        pygame.quit()

    def handle_race_end(self, winner):
        """
        Routes race results to the active session manager.
        """
        if self.settings["mode"] == "ARCADE":
            self.arcade.record_win(winner)
            if self.arcade.is_finished():
                self.state = "arcade_results"
            else:
                self.state = "arcade_transition"
                self.transition_timer = 3.0

        elif self.settings["mode"] == "GRAND_PRIX":
            self.grand_prix.record_win(winner)
            self.grand_prix.next_race()
            if self.grand_prix.is_finished():
                self.state = "gp_results"
            else:
                self.state = "gp_transition"
                self.transition_timer = 3.0

        elif self.settings["mode"] == "AI_OPP":
            self.ai_opp.record_win(winner)
            print(f"Race Over. Winner: {winner}")
            self.state = "menu"
            self.menu_substate = "root"
            # Re-init background track for menu so it's not black
            self.track_data = generate_track(50, 10, seed=555)
            self.game_ux = GameUX(
                self.screen,
                self.track_data,
                self.player_car,
                self.ai_car,
                {"mode": "MENU"},
            )
