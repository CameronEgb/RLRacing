# game.py
import pygame
import math
from config import *
from .track_generator import generate_track
from .car import Car
from ui.ux import GameUX
from ai.random_ai_opponent import RandomAIOpponent
# from ai.ai_opponent import AIOpponent  # Uncomment when ready
from utils import compute_grid_positions
from modes.arcade_mode import ArcadeSession
from modes.grand_prix_mode import GrandPrixSession

ChosenAIOpponent = RandomAIOpponent  # Switch to AIOpponent for RL

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("RLRacing – RL-ready")
        self.clock = pygame.time.Clock()

        self.state = "menu"
        self.menu_substate = "root"

        self.settings = {
            "mode": "ARCADE",
            "difficulty": "NORMAL",
            "weather": "CLEAR",
            "track_width": 50,
            "complexity": 10,
            "gp_cup_index": 0,
        }
        self.pending = self.settings.copy()

        self.track_data = None
        self.player_car = self.ai_car = None
        self.ai_opponent = None
        self.game_ux = None

        self.player_spawn = self.ai_spawn = (0, 0)
        self.player_active = self.ai_active = False

        self.arcade = ArcadeSession()
        self.grand_prix = GrandPrixSession()

        self.countdown_timer = 0.0
        self.transition_timer = 0.0

        self.build_world(self.settings)

    def build_world(self, settings):
        seed = settings.get("seed")
        self.track_data = generate_track(
            width=settings["track_width"],
            complexity=settings["complexity"],
            seed=seed
        )

        for cp in self.track_data.get("checkpoints", []):
            cp["player_reached"] = cp["ai_reached"] = False

        p_pos, a_pos = compute_grid_positions(self.track_data)
        angle = self.track_data["start_angle"]

        self.player_car = Car(*p_pos, angle, (100, 150, 255), name="Player")
        self.ai_car = Car(*a_pos, angle, (255, 150, 100), name="AI Opponent")

        self.ai_opponent = ChosenAIOpponent(self.ai_car, self.track_data)

        meta = {**settings, "track_name": settings.get("track_name")}
        self.game_ux = GameUX(self.screen, self.track_data, self.player_car, self.ai_car, meta)

        for car in (self.player_car, self.ai_car):
            if hasattr(car, "set_difficulty"):
                car.set_difficulty(settings["difficulty"])
            if hasattr(car, "set_weather"):
                car.set_weather(settings["weather"])

        self.player_spawn = p_pos
        self.ai_spawn = a_pos
        self.player_active = self.ai_active = False

    def run(self):
        from states import get_state_handler
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            handler = get_state_handler(self)
            if handler(self, dt) is False:
                running = False
        pygame.quit()

    def handle_race_end(self, winner):
        if self.arcade.active:
            self.arcade.record_win(winner)
            if self.arcade.is_finished():
                self.state = "arcade_results"
            else:
                self.state = "arcade_transition"
                self.transition_timer = 3.0

        elif self.grand_prix.active:
            self.grand_prix.record_win(winner)
            self.grand_prix.next_race()
            if self.grand_prix.is_finished():
                self.state = "gp_results"
            else:
                self.state = "gp_transition"
                self.transition_timer = 3.0
        else:
            # Single race (no session)
            self.state = "menu"
            self.menu_substate = "root"