import math
import random
import numpy as np
from typing import Dict, List, Tuple
from collections import deque
from car import Car
from stable_baselines3 import PPO
from env_wrapper import RacingEnv, _ACTIONS
import pygame  # For surfarray and transform

class AIOpponent:
    """
    AI opponent controller for racing game.
    Integrates trained PPO RL agent for realistic racing behavior.
    Replaces placeholder with model-driven actions based on pixel observations.
    """
    
    def __init__(self, car: Car, track_data: Dict, model_path: str = "models/ppo_race_quick_custom_200000_steps"):
        self.car = car
        self.track_data = track_data
        
        # Load trained PPO agent
        print(f"Loading RL agent from {model_path}...")
        self.model = PPO.load(model_path)
        print(f"loaded the model")
        
        # Create env for AI observations (same track)
        self.ai_env = RacingEnv(
            screen_size=(640, 640),
            obs_size=(64, 64),
            action_repeat=2,
            max_episode_seconds=45.0,
            render_mode='rgb_array',  # For pixel obs
            # No track_kwargs—pass track via reset options
        )
        self.ai_env.reset(options={"track": track_data})  # Use game's exact track
        
        # Sync initial game AI car to env
        self._sync_car_to_env()
        
        # Frame stack for observations (n_stack=6 for gray channels-last)
        self.frames = deque(maxlen=6)
        self._initialize_frame_stack()
        
        # AI behavior parameters (optional overrides for RL)
        self.skill_level = 1.0  # Full RL capability
        self.aggressiveness = 0.5  # Not used with RL, but kept for compatibility
        
        # State tracking
        self.last_position = (car.x, car.y)
        self.stuck_timer = 0
    
    def _sync_car_to_env(self):
        """Sync game car state to env's internal car."""
        self.ai_env.car.x = self.car.x
        self.ai_env.car.y = self.car.y
        self.ai_env.car.angle = self.car.angle
        # Sync velocities if env uses them for render/physics
        self.ai_env.car.velocity_x = getattr(self.car, 'velocity_x', 0.0)
        self.ai_env.car.velocity_y = getattr(self.car, 'velocity_y', 0.0)
        self.ai_env.car.angular_velocity = getattr(self.car, 'angular_velocity', 0.0)
    
    def _initialize_frame_stack(self):
        """Initialize frame stack with initial grayscale observations."""
        full_obs = self.ai_env.render(mode="rgb_array")
        if full_obs is None:
            raise ValueError("Failed to render initial observation—check env setup.")
        initial_obs = np.squeeze(full_obs.astype(np.uint8), axis=-1)  # (64,64)
        self.frames.clear()  # Reset if needed
        for _ in range(6):
            self.frames.append(initial_obs)
    
    def update(self, dt: float):
        """
        Update AI opponent using RL agent.
        Syncs state, gets stacked pixel obs, predicts action, applies to car.
        """
        # Sync current game state to env for accurate observation
        self._sync_car_to_env()
        
        # Get current observation (grayscale)
        full_obs = self.ai_env.render(mode="rgb_array")
        if full_obs is None:
            print("Warning: Render returned None—falling back to no-op.")
            throttle, steering = _ACTIONS[4]  # Default to "nothing"
            self.car.set_input(throttle, steering)
            self._check_stuck_state(dt)
            return
        obs = full_obs.astype(np.uint8)  # (64,64,1)
        
        # Update frame stack: append latest (squeeze channel for stack), stack channels-last
        obs_flat = np.squeeze(obs, axis=-1)  # (64,64)
        self.frames.append(obs_flat)
        stacked_obs = np.stack(list(self.frames), axis=-1)  # (64, 64, 6) channels-last gray
        
        # Add batch dimension for stable SB3 inference (mimics VecEnv)
        stacked_obs = stacked_obs[None, ...]  # (1, 64, 64, 6)
        
        # Predict action from RL model (deterministic for consistency)
        action, _ = self.model.predict(stacked_obs, deterministic=True)
        action_idx = int(action[0]) if isinstance(action, np.ndarray) else int(action)  # Unbatch; handle discrete
        
        # Map discrete action to (throttle, steering)
        throttle, steering = _ACTIONS[action_idx]
        
        self.car.set_input(throttle, steering)
        
        # Check if stuck (RL should handle, but backup nudge)
        self._check_stuck_state(dt)
    
    def _check_stuck_state(self, dt: float):
        """Backup check for stuck state (rare with RL)."""
        current_pos = (self.car.x, self.car.y)
        distance_moved = math.hypot(
            current_pos[0] - self.last_position[0], 
            current_pos[1] - self.last_position[1]
        )
        
        if distance_moved < 5.0:
            self.stuck_timer += dt
        else:
            self.stuck_timer = 0
            self.last_position = current_pos
        
        # If stuck too long, small intervention
        if self.stuck_timer > 10.0:
            self.car.set_input(0.5, random.uniform(-0.3, 0.3))
            self.stuck_timer = 0
    
    def set_difficulty(self, skill: float, aggressiveness: float):
        """
        Adjust parameters (minimal effect on RL; for future hybrid modes).
        """
        self.skill_level = max(0.0, min(1.0, skill))
        self.aggressiveness = max(0.0, min(1.0, aggressiveness))
    
    def reset_position(self, x: float, y: float, angle: float):
        """Reset AI car and reinitialize RL state."""
        self.car.x = x
        self.car.y = y
        self.car.angle = angle
        self.car.velocity_x = 0.0
        self.car.velocity_y = 0.0
        self.car.angular_velocity = 0.0
        
        # Reset env and stack (pass track to keep same track)
        self.ai_env.reset(options={"track": self.track_data})
        self._sync_car_to_env()
        self._initialize_frame_stack()
        
        # Reset state
        self.stuck_timer = 0
        self.last_position = (x, y)
    
    def close(self):
        """Cleanup env on shutdown."""
        self.ai_env.close()