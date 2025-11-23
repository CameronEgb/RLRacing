"""
Gym/Gymnasium wrapper for top-down racing sim.
Reconstructed to support:
1. Persistent tracks (passed via options or init)
2. Advanced Reward function (Checkpoints, Wall Penalties, Grass Penalties)
"""

import os
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
import pygame
from pygame import surfarray

from game.car import Car
from game.track_generator import generate_track

# Conditional headless setup
if os.environ.get("IS_TRAINING") == "true" and "SDL_VIDEODRIVER" not in os.environ:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

# Action mapping
_ACTIONS = {
    0: (0.0, -1.0),   # left
    1: (0.0, 1.0),    # right
    2: (1.0, 0.0),    # accelerate
    3: (-1.0, 0.0),   # brake / reverse
    4: (0.0, 0.0),    # nothing
}

class RacingEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}

    def __init__(self,
                 screen_size=(640, 640),
                 obs_size=(64, 64),
                 action_repeat=4,
                 max_episode_seconds=60.0, # Increased for full laps
                 render_mode=None,
                 track_data=None): # Can pass a fixed track here
        
        self.screen_width, self.screen_height = screen_size
        self.obs_size = obs_size
        self.action_repeat = action_repeat
        self.max_episode_steps = int(max_episode_seconds * 30)
        self.render_mode = render_mode
        self.fixed_track = track_data

        # Initialize Pygame
        if not pygame.get_init():
            pygame.init()
            pygame.display.init()

        if self.render_mode == "human":
            self.screen = pygame.display.set_mode(screen_size)
        else:
            self.screen = pygame.Surface(screen_size)

        # Observation Space: Grayscale 64x64
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(obs_size[0], obs_size[1], 1), dtype=np.uint8
        )

        # Action Space: Discrete 5
        self.action_space = spaces.Discrete(5)

        self.clock = pygame.time.Clock()
        self.car = None
        self.track = None
        self.step_count = 0
        
        # Tracking for rewards
        self.next_checkpoint_idx = 0
        self.lap_count = 0
        self.prev_distance_to_checkpoint = 0.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        # 1. Track Selection
        if options and "track" in options:
            self.track = options["track"]
        elif self.fixed_track:
            self.track = self.fixed_track
        else:
            # Fallback to random generation if no track provided
            self.track = generate_track(seed=seed if seed else 100)

        # 2. Car Initialization
        sx, sy = self.track["start_pos"]
        sa = self.track["start_angle"]
        self.car = Car(sx, sy, sa, (255, 0, 0), name="Agent")

        # 3. Reset State Tracking
        self.step_count = 0
        self.next_checkpoint_idx = 1 # Start aiming for the first real checkpoint (0 is usually start)
        self.lap_count = 0
        
        # Initial distance to target
        self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)

        # Initial Render
        self._draw_frame()
        return self._render_obs(), {}

    def step(self, action_idx):
        total_reward = 0.0
        terminated = False
        truncated = False
        
        throttle, steering = _ACTIONS[action_idx]
        
        # Action Repeat for stability
        for _ in range(self.action_repeat):
            # --- FIXED UPDATE CALL ---
            # Separate input setting from update loop to match Car class interface
            self.car.set_input(throttle, steering)
            self.car.update(1.0 / 30.0, self.track)
            
            # --- REWARD CALCULATION ---
            
            # 1. Progress Reward (Checkpoint based)
            dist_to_cp = self._dist_to_checkpoint(self.next_checkpoint_idx)
            progress = self.prev_distance_to_checkpoint - dist_to_cp
            total_reward += progress * 0.1  # Reward moving closer
            self.prev_distance_to_checkpoint = dist_to_cp
            
            # Check if checkpoint reached (within 40 pixels)
            if dist_to_cp < 40:
                total_reward += 2.0  # BIG bonus for hitting checkpoint
                self.next_checkpoint_idx = (self.next_checkpoint_idx + 1) % len(self.track["checkpoints"])
                self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)
                
                # Lap completion check
                if self.next_checkpoint_idx == 0:
                    self.lap_count += 1
                    total_reward += 5.0 # Lap bonus

            # 2. Speed Reward (Encourage going fast)
            speed = self.car.get_speed_kmh()
            total_reward += speed * 0.005
            
            # 3. Penalties (Walls & Grass)
            # We calculate distance from the centerline
            track_width = self.track["width"]
            dist_from_center = self._dist_to_centerline()
            
            # Thresholds
            on_grass_thresh = (track_width / 2) * 0.8
            hit_wall_thresh = (track_width / 2)
            
            if dist_from_center > hit_wall_thresh:
                # Wall Collision
                total_reward -= 5.0 # Heavy penalty
                terminated = True   # End episode on crash? (Optional, helps learning safety)
            elif dist_from_center > on_grass_thresh:
                # Grass
                total_reward -= 0.1 # Constant drag penalty
        
        self.step_count += 1
        if self.step_count >= self.max_episode_steps:
            truncated = True

        self._draw_frame()
        obs = self._render_obs()
        
        return obs, total_reward, terminated, truncated, {}

    def _dist_to_checkpoint(self, idx):
        # Handle wrapping if track varies slightly
        if idx >= len(self.track["checkpoints"]): idx = 0
        
        cp = self.track["checkpoints"][idx]
        
        # Robust extraction to handle different track_generator formats
        if isinstance(cp, dict):
            if "pos" in cp:
                cx, cy = cp["pos"]
            elif "x" in cp and "y" in cp:
                cx, cy = cp["x"], cp["y"]
            elif "center" in cp:
                cx, cy = cp["center"]
            else:
                # Fallback for unknown dict structure
                cx, cy = 0, 0
        else:
            # Assume list or tuple [x, y]
            cx, cy = cp[0], cp[1]

        return math.hypot(self.car.x - cx, self.car.y - cy)

    def _dist_to_centerline(self):
        """Finds distance to the closest point on the centerline."""
        # This is a naive O(N) search. For performance, could use spatial hashing,
        # but for <1000 points it's fine.
        min_dist = float('inf')
        for px, py in self.track["centerline"]:
            d = math.hypot(self.car.x - px, self.car.y - py)
            if d < min_dist:
                min_dist = d
        return min_dist

    def _draw_frame(self):
        # Simple draw for AI observation
        self.screen.fill((70, 105, 70))  # Grass
        
        # Draw track (simplified for AI: Gray asphalt)
        try:
            pygame.draw.polygon(self.screen, (45, 45, 45), self.track["outer_boundary"])
            pygame.draw.polygon(self.screen, (70, 105, 70), self.track["inner_boundary"])
        except:
            # Fallback if boundaries aren't valid polygons
            pass

        # Draw Car
        # We need the car's corners to draw a rotated rectangle
        pts = self.car.get_corners()
        pygame.draw.polygon(self.screen, (255, 0, 0), pts)
        
        if self.render_mode == "human":
            pygame.display.flip()

    def _render_obs(self):
        surf = self.screen
        # Convert Surface to Array
        arr_rgb = surfarray.array3d(surf) # W,H,3
        arr_rgb = np.transpose(arr_rgb, (1, 0, 2)) # H,W,3
        
        # Grayscale
        gray = np.dot(arr_rgb[..., :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
        
        # Scale
        obs_surf = pygame.transform.smoothscale(surf, self.obs_size)
        arr_scaled = surfarray.array3d(obs_surf)
        arr_scaled = np.transpose(arr_scaled, (1, 0, 2))
        gray_scaled = np.dot(arr_scaled[..., :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
        
        return gray_scaled[:, :, np.newaxis]

    def close(self):
        if self.screen:
            pygame.quit()