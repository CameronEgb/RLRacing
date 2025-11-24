import os
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
import pygame
from observation import VisionProcessor 
from game.car import Car

# Conditional headless setup
if os.environ.get("IS_TRAINING") == "true" and "SDL_VIDEODRIVER" not in os.environ:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

class RacingEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}

    def __init__(self,
                 screen_size=(640, 640),
                 obs_size=(64, 64),
                 action_repeat=4,
                 max_episode_seconds=12.5,
                 render_mode=None,
                 track_data=None,
                 action_type="continuous",
                 obs_type="VISION"): # <--- ADDED OBS_TYPE ARGUMENT
        
        self.screen_width, self.screen_height = screen_size
        self.obs_size = obs_size
        self.action_repeat = action_repeat
        self.max_episode_steps = int(max_episode_seconds * 30)
        self.render_mode = render_mode
        self.fixed_track = track_data
        self.action_type = action_type
        self.obs_type = obs_type # <--- STORE IT

        # Initialize Vision/Observation Processor
        self.vision = VisionProcessor(obs_size=obs_size)

        if not pygame.get_init():
            pygame.init()
            pygame.display.init()

        if self.render_mode == "human":
            self.screen = pygame.display.set_mode(screen_size)
        else:
            self.screen = pygame.Surface(screen_size)

        # --- DYNAMIC OBSERVATION SPACE ---
        if self.obs_type == "VISION":
            # (H, W, 1) Grayscale Image [0-255]
            self.observation_space = spaces.Box(
                low=0, high=255, shape=(obs_size[0], obs_size[1], 1), dtype=np.uint8
            )
        elif self.obs_type == "NUMERIC":
            # (11,) Vector [Rays(9) + Speed(1) + Steer(1)]
            # Ranges are roughly 0.0 to 1.0 (normalized), but we allow -inf/inf for safety
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf, shape=(11,), dtype=np.float32
            )
        else:
            raise ValueError(f"Unknown obs_type: {self.obs_type}")

        # Action Space
        if self.action_type == "continuous":
            # [Throttle, Steering]
            self.action_space = spaces.Box(
                low=-1.0, high=1.0, shape=(2,), dtype=np.float32
            )
        elif self.action_type == "multi_discrete":
            # [Steering (0=L, 1=C, 2=R), Throttle (0=Br, 1=N, 2=Acc)]
            self.action_space = spaces.MultiDiscrete([3, 3])
        else:
            raise ValueError("Invalid action_type. Use 'continuous' or 'multi_discrete'")

        self.clock = pygame.time.Clock()
        self.car = None
        self.track = None
        self.step_count = 0
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
            raise Exception("Can't find track")

        # 2. Car Initialization
        sx, sy = self.track["start_pos"]
        sa = self.track["start_angle"]
        sa = math.degrees(sa) 

        self.car = Car(sx, sy, sa, (255, 0, 0), name="Agent", weather=self.track['intended_weather'])

        # 3. Reset State Tracking
        self.step_count = 0
        self.next_checkpoint_idx = 1
        self.lap_count = 0
        self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)

        obs = self._render_obs()
        return obs, {}

    def step(self, action):
        total_reward = 0.0
        terminated = False
        truncated = False

        # 1. Unpack Action
        throttle = 0.0
        steering = 0.0

        if self.action_type == "continuous":
            throttle = float(action[0])
            steering = float(action[1])
            throttle = np.clip(throttle, -1.0, 1.0)
            steering = np.clip(steering, -1.0, 1.0)
        elif self.action_type == "multi_discrete":
            steering = float(action[0] - 1)
            throttle = float(action[1] - 1)

        if throttle < 0: throttle = 0

        # 2. Physics Steps + Reward Calc
        for _ in range(self.action_repeat):
            # --- ACTION & PHYSICS UPDATE ---
            self.car.set_input(throttle, steering)
            self.car.update(1.0 / 30.0, self.track)

            # --- REWARD CALCULATION ---
            step_reward = 0.0
            
            # 1. Time Penalty
            step_reward -= 0.05

            # 2. Progress Reward
            dist_to_cp = self._dist_to_checkpoint(self.next_checkpoint_idx)
            raw_progress = self.prev_distance_to_checkpoint - dist_to_cp
        
            # Clamp to prevent glitches
            raw_progress = max(min(raw_progress, 10.0), -10.0)
        
            # Scale
            step_reward += raw_progress * 0.3

            self.prev_distance_to_checkpoint = dist_to_cp

            # 3. Checkpoints & Laps
            if dist_to_cp < 40:
                step_reward += 2.0
                self.next_checkpoint_idx = (self.next_checkpoint_idx + 1) % len(self.track["checkpoints"])
                self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)
            
                if self.next_checkpoint_idx == 0:
                    self.lap_count += 1
                    step_reward += 10.0

            # 4. Centering Penalty
            track_half_width = self.track["width"] / 2
            dist_from_center = self._dist_to_centerline()
            norm_dist = dist_from_center / track_half_width

            if norm_dist > 1.0:
                step_reward -= 5.0 
                terminated = True
            else:
                step_reward -= (norm_dist ** 4) * 0.5

            total_reward += step_reward
            
            # Break sub-step loop if terminal
            if terminated:
                break

        self.step_count += 1
        if self.step_count >= self.max_episode_steps:
            truncated = True

        self._draw_frame()
        obs = self._render_obs()
        
        return obs, total_reward, terminated, truncated, {}

    def _render_obs(self):
        # PASS self.obs_type to the processor
        obs = self.vision.get_observation(self.car, self.track, obs_type=self.obs_type)
        return obs

    def _draw_frame(self):
        if self.render_mode == "human":
            self.screen.fill((70, 105, 70))
            if self.track:
                pygame.draw.polygon(self.screen, (45, 45, 45), self.track["outer_boundary"])
                pygame.draw.polygon(self.screen, (70, 105, 70), self.track["inner_boundary"])
            
            pts = self.car.get_corners()
            pygame.draw.polygon(self.screen, (255, 0, 0), pts)
            pygame.display.flip()

    def _dist_to_checkpoint(self, idx):
        if idx >= len(self.track["checkpoints"]): idx = 0
        cp = self.track["checkpoints"][idx]
        if isinstance(cp, dict):
            if "pos" in cp: cx, cy = cp["pos"]
            elif "x" in cp and "y" in cp: cx, cy = cp["x"], cp["y"]
            elif "center" in cp: cx, cy = cp["center"]
            else: cx, cy = 0, 0
        else:
            cx, cy = cp[0], cp[1]
        return math.hypot(self.car.x - cx, self.car.y - cy)

    def _dist_to_centerline(self):
        min_dist = float('inf')
        # Optimization: Only search segment near current checkpoint index
        # But brute force is fine for < 1000 points
        for px, py in self.track["centerline"]:
            d = math.hypot(self.car.x - px, self.car.y - py)
            if d < min_dist:
                min_dist = d
        return min_dist