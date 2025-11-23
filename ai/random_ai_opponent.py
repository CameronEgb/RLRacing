# New file: random_ai_opponent.py
import random
from typing import Dict
from game.car import Car

# Assuming _ACTIONS is defined elsewhere (e.g., import from env_wrapper if needed).
# For this example, I'll define a placeholder _ACTIONS here. Replace with the actual one from your env_wrapper.
_ACTIONS = [
    (0.0, 0.0),    # No input
    (1.0, 0.0),    # Full throttle, straight
    (1.0, 0.5),    # Full throttle, right
    (1.0, -0.5),   # Full throttle, left
    (0.0, 0.5),    # Brake/Reverse, right
    (0.0, -0.5),   # Brake/Reverse, left
    (-1.0, 0.0),   # Full reverse, straight
    (0.5, 0.0),    # Half throttle
    # Add more as per your actual _ACTIONS list (aim for 5-9 discrete actions for variety)
]

class RandomAIOpponent:
    """
    Simple randomized AI opponent for racing game.
    Picks a random action from predefined discrete actions each update.
    Mimics the interface of AIOpponent for easy swapping.
    """
    
    def __init__(self, car: Car, track_data: Dict):
        self.car = car
        self.track_data = track_data  # Kept for compatibility, but unused here
        
        # AI behavior parameters (optional, for future tweaks)
        self.skill_level = 1.0  # Not used in random mode
        self.aggressiveness = 0.5  # Not used in random mode
        
        # State tracking for optional stuck detection (disabled by default for pure random)
        self.enable_stuck_check = False
        self.last_position = (car.x, car.y)
        self.stuck_timer = 0
    
    def update(self, dt: float):
        """
        Update AI opponent with a random action.
        Applies to car via set_input.
        """
        # Pick random action
        throttle, steering = random.choice(_ACTIONS)
        
        # Optional: Bias towards forward actions based on aggressiveness (e.g., more throttle)
        #if self.aggressiveness > 0.5 and random.random() < 0.7:
            # Favor positive throttle actions
        #    forward_actions = [(t, s) for t, s in _ACTIONS if t > 0]
        #    if forward_actions:
        #        throttle, steering = random.choice(forward_actions)
        
        self.car.set_input(throttle, steering)
        
        # Optional stuck check (if enabled)
        if self.enable_stuck_check:
            self._check_stuck_state(dt)
    
    def _check_stuck_state(self, dt: float):
        """Backup nudge if stuck too long (rare with random actions)."""
        current_pos = (self.car.x, self.car.y)
        distance_moved = ((current_pos[0] - self.last_position[0]) ** 2 + 
                          (current_pos[1] - self.last_position[1]) ** 2) ** 0.5
        
        if distance_moved < 5.0:
            self.stuck_timer += dt
        else:
            self.stuck_timer = 0
            self.last_position = current_pos
        
        if self.stuck_timer > 5.0:  # Shorter timer for random mode
            self.car.set_input(1.0, random.uniform(-0.5, 0.5))  # Nudge forward
            self.stuck_timer = 0
    
    def set_difficulty(self, skill: float, aggressiveness: float):
        """
        Adjust parameters (affects random bias if aggressiveness > 0.5).
        """
        self.skill_level = max(0.0, min(1.0, skill))
        self.aggressiveness = max(0.0, min(1.0, aggressiveness))
        # Optionally enable stuck check for lower skill
        self.enable_stuck_check = skill < 0.5
    
    def reset_position(self, x: float, y: float, angle: float):
        """Reset AI car position and angle."""
        self.car.x = x
        self.car.y = y
        self.car.angle = angle
        self.car.velocity_x = 0.0
        self.car.velocity_y = 0.0
        self.car.angular_velocity = 0.0
        
        # Reset state
        self.stuck_timer = 0
        self.last_position = (x, y)
    
    def close(self):
        """No-op cleanup for compatibility."""
        pass