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
        # Generate a dummy track so the menu has something to render (transparency fix)
        self.track_data = generate_track(50, 10, seed=555)
        
        # Initialize dummy cars for the menu view
        start_pos = self.track_data["start_pos"]
        start_angle = self.track_data["start_angle"]
        
        # FIX: Updated Car instantiation to match car.py signature
        # Car(x, y, angle, color, name)
        self.player_car = Car(start_pos[0], start_pos[1], start_angle, (0, 120, 255), name="Player")
        self.ai_car = Car(start_pos[0] - 50, start_pos[1], start_angle, (200, 0, 0), name="AI")
        
        # Setup Initial UX for Menu Background
        self.game_ux = GameUX(self.screen, self.track_data, self.player_car, self.ai_car, {"mode": "MENU"})
        # Center camera on start for menu
        self.game_ux.camera_offset = (
            start_pos[0] - SCREEN_WIDTH // 2,
            start_pos[1] - SCREEN_HEIGHT // 2
        )

        self.ai_opponent = None
        self.player_spawn = self.ai_spawn = (0, 0)
        self.player_active = self.ai_active = False

        # Sessions
        self.arcade = ArcadeSession()
        self.grand_prix = GrandPrixSession()
        self.ai_opp = AIOppSession()

        self.transition_timer = 0.0

    def start_race(self, settings=None):
        """
        Initializes a race based on current pending settings.
        """
        # Apply settings
        if not settings:
            self.settings = self.pending.copy()
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
            self.track_data = generate_track(t_conf["width"], t_conf["complexity"], t_conf["seed"])
            if not self.grand_prix.active:
                self.grand_prix.start(self.settings["gp_cup_index"], self.settings["difficulty"], self.settings["weather"])
                
        else: # ARCADE
            # Generate random track
            self.track_data = generate_track(
                self.settings["track_width"], 
                self.settings["complexity"], 
                seed=None # Random
            )
            if not self.arcade.active:
                self.arcade.start()

        # 2. Setup Cars
        start_angle = self.track_data["start_angle"]
        
        # FIX: Pass the full self.track_data dictionary to utils
        p_pos, a_pos = compute_grid_positions(self.track_data)
        
        # FIX: Updated Car instantiation to match car.py signature
        # Using Blue for Player, Red for AI
        self.player_car = Car(p_pos[0], p_pos[1], start_angle, (0, 120, 255), name="Player", weather=self.track_data["intended_weather"])
        self.ai_car = Car(a_pos[0], a_pos[1], start_angle, (200, 0, 0), name="AI", weather=self.track_data["intended_weather"])
        
        # 3. Setup AI Agent
        if mode == "AI_OPP":
            if self.ai_opp.model_path:
                # --- CRITICAL FIX: PASS OBS_TYPE TO OPPONENT ---
                self.ai_opponent = RLAIOpponent(
                    self.ai_car, 
                    self.ai_opp.model_path, 
                    obs_type=self.ai_opp.obs_type # <--- Handshake here
                )
            else:
                print("No model found, placeholding with Random AI fallback agent.")
                self.ai_opponent = RandomAIOpponent(self.ai_car, self.track_data)
                self.ai_opponent.set_difficulty(1, 1)
        else:
            self.ai_opponent = RandomAIOpponent(self.ai_car, self.track_data)
            self.ai_opponent.set_difficulty(1, 1)

        # 4. Setup UX
        meta = {
            "mode": mode,
            "track_name": self.ai_opp.track_name if mode == "AI_OPP" else "Procedural Track"
        }
        self.game_ux = GameUX(self.screen, self.track_data, self.player_car, self.ai_car, meta)

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
            self.game_ux = GameUX(self.screen, self.track_data, self.player_car, self.ai_car, {"mode": "MENU"})