# env_wrapper.py
"""
Gym/Gymnasium wrapper for your top-down racing sim (Car class + track generator).
Observations: downscaled GRAYSCALE frames (64x64x1), dtype=np.uint8
Action space: Discrete(5) -> [left, right, accelerate, brake, nothing]
This wrapper tries to be minimally invasive and works headless (SDL_VIDEODRIVER=dummy).
"""

import os
import math
import random
import numpy as np
import gymnasium as gym
from gymnasium import spaces

# Conditional headless setup: Only dummy if explicitly in training mode
if os.environ.get("IS_TRAINING") == "true" and "SDL_VIDEODRIVER" not in os.environ:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
from pygame import Surface, surfarray

# Import your project classes (adjust import path if needed)
from car import Car
from track_generator import generate_track  # adjust if function different

# action mapping: macro actions to (throttle, steering)
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
                 action_repeat=2,
                 max_episode_seconds=60.0,
                 render_mode=None,
                 track_kwargs=None):
        super().__init__()

        self.screen_size = screen_size
        self.obs_size = obs_size
        self.action_repeat = action_repeat
        self.max_episode_seconds = max_episode_seconds
        self.render_mode = render_mode
        self.track_kwargs = track_kwargs or {}

        # Discrete(5) actions
        self.action_space = spaces.Discrete(len(_ACTIONS))

        # Observations: uint8 GRAYSCALE image (H,W,1) for explicit channel
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(obs_size[0], obs_size[1], 1), dtype=np.uint8
        )

        # Pygame surfaces for rendering frames
        pygame.init()
        self._screen = None
        self._surface = Surface(self.screen_size)

        # placeholders
        self.track = None
        self.car = None
        self._elapsed = 0.0
        self._last_progress_index = None

    def seed(self, seed=None):
        np.random.seed(seed)
        random.seed(seed)
        return [seed]

    def close(self):
        try:
            pygame.quit()
        except Exception:
            pass

    def reset(self, seed=None, options=None):
        if options is None:
            options = {}
        
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)
        
        if "track" in options:
            self.track = options["track"]
        else:
            self.track = generate_track(**(self.track_kwargs or {}))

        # Create a Car instance at starting position.
        rl = self.track.get("racing_line", None)
        if rl and len(rl) > 0:
            sx, sy = rl[0]
            angle = self.track.get("start_angle", 0.0)
        else:
            sx, sy, angle = 0.0, 0.0, 0.0

        self.car = Car(x=sx, y=sy, angle=angle)

        self._elapsed = 0.0
        self._last_progress_index = 0

        obs = self._render_obs()
        info = {}
        return obs, info

    # --- helper: compute a simple "progress" estimate along racing_line
    def _compute_progress_index(self):
        rl = self.track.get("racing_line", None)
        if rl is None or len(rl) == 0:
            return 0
        # find closest point index
        cx, cy = self.car.x, self.car.y
        dmin = float("inf"); idx = 0
        for i, p in enumerate(rl):
            dx = p[0] - cx; dy = p[1] - cy
            d = dx*dx + dy*dy
            if d < dmin:
                dmin = d; idx = i
        return idx

    def _off_track_penalty(self):
        # Simple heuristic: track might have a 'road_mask' or tilemap. If not available,
        # return 0. If you have a function to test off-road, plug it here.
        # For now we check distance to racing line: too far -> penalty.
        rl = self.track.get("racing_line", None)
        if not rl:
            return 0.0
        cx, cy = self.car.x, self.car.y
        # distance to closest racing line point
        dmin = min(math.hypot(p[0]-cx, p[1]-cy) for p in rl)
        if dmin > 20.0:  # tuned to your pixel/world scale
            return -0.5
        return 0.0

    def step(self, action):
        assert self.action_space.contains(action), action
        throttle, steering = _ACTIONS[int(action)]

        # Apply macro action for several internal simulation steps
        reward = 0.0
        done = False
        info = {}

        # apply repeated small steps to simulate motor steps per env step
        for _ in range(self.action_repeat):
            # apply input
            self.car.set_input(throttle, steering)

            # advance simulation - this assumes your Car.update(dt, track) API
            dt = 1.0 / 60.0  # choose physics step
            # If your project has a central update loop requiring track, call that
            # Here we assume Car.update(dt, track)
            try:
                self.car.update(dt, self.track)
            except TypeError:
                # fallback in case signature differs
                self.car.update(dt)

            # incremental reward: forward progress proxy
            # approximate forward component of velocity in heading direction
            vx = getattr(self.car, "velocity_x", 0.0)
            vy = getattr(self.car, "velocity_y", 0.0)
            speed = math.hypot(vx, vy)
            heading = getattr(self.car, "angle", 0.0)
            # project velocity onto heading
            forward = vx * math.cos(heading) + vy * math.sin(heading)
            reward += max(0.0, forward) * 0.01

            # small alive bonus
            reward += 0.001

            # off-track penalty
            reward += self._off_track_penalty()

            self._elapsed += dt
            if self._elapsed >= self.max_episode_seconds:
                done = True

        # termination if car is nearly stationary and far off track (optional)
        if speed < 0.1 and self._off_track_penalty() < -0.1:
            done = True

        obs = self._render_obs()
        return obs, float(reward), bool(done), False, {}  # gymnasium: (obs, reward, terminated, truncated, info)

    def _render_obs(self):
        # Render game to a pygame surface and return downscaled GRAYSCALE uint8 array (H,W,1).
        surf = self._surface
        surf.fill((0, 0, 0))  # Black bg

        # Draw racing_line if present (white)
        rl = self.track.get("racing_line", None)
        if rl:
            points = [(int(x + self.screen_size[0] // 2), int(y + self.screen_size[1] // 2)) for (x, y) in rl]
            if len(points) >= 2:
                pygame.draw.lines(surf, (200, 200, 200), False, points, 4)

        # Draw car as triangle (red)
        cx = int(self.car.x + self.screen_size[0] // 2)
        cy = int(self.car.y + self.screen_size[1] // 2)
        ang = -self.car.angle
        size = 8
        points = [
            (cx + int(math.cos(ang) * size), cy + int(math.sin(ang) * size)),
            (cx + int(math.cos(ang + 2.3) * size), cy + int(math.sin(ang + 2.3) * size)),
            (cx + int(math.cos(ang - 2.3) * size), cy + int(math.sin(ang - 2.3) * size)),
        ]
        pygame.draw.polygon(surf, (255, 0, 0), points)

        # Convert to array (H,W,3) → grayscale (H,W)
        arr_rgb = surfarray.array3d(surf)  # (W,H,3)
        arr_rgb = np.transpose(arr_rgb, (1, 0, 2))  # (H,W,3)
        # RGB to gray: weighted sum
        gray = np.dot(arr_rgb[..., :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)  # (H,W)

        # Downscale to obs_size (H,W)
        obs_surf = pygame.transform.smoothscale(surf, self.obs_size)  # Scale full surface
        arr_scaled_rgb = surfarray.array3d(obs_surf)  # (W,H,3)
        arr_scaled_rgb = np.transpose(arr_scaled_rgb, (1, 0, 2))  # (H,W,3)
        obs_gray = np.dot(arr_scaled_rgb[..., :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)  # (H,W)

        return obs_gray[:,:,np.newaxis]  # Shape: (64, 64, 1), uint8

    def render(self, mode="human"):
        if mode == "rgb_array":
            # For AI, return gray (H,W,1)
            return self._render_obs()
        if mode == "human":
            if self._screen is None:
                self._screen = pygame.display.set_mode(self.screen_size)
            # For human, render RGB version
            surf_rgb = self._surface.copy()
            frame_rgb = surfarray.array3d(surf_rgb)  # (W,H,3)
            frame_rgb = np.transpose(frame_rgb, (1, 0, 2))  # (H,W,3)
            surface = pygame.surfarray.make_surface(frame_rgb)
            self._screen.blit(surface, (0, 0))
            pygame.display.flip()
            return None

    def seed(self, seed=None):
        np.random.seed(seed)
        random.seed(seed)
        return [seed]