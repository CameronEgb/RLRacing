import pygame
import numpy as np
import os
from collections import deque
from ai.observation import VisionProcessor 

# Try importing SB3
try:
    from stable_baselines3 import PPO
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    print("Warning: stable_baselines3 not installed.")

class RLAIOpponent:
    def __init__(self, car, model_path, obs_type="VISION", debug=True):
        self.car = car
        self.model = None
        self.debug = debug
        self.debug_step = 0
        self.obs_type = obs_type # Store the type passed from Game/Session
        
        self.vision = VisionProcessor(obs_size=(64, 64))
        
        # Buffer to store the last 4 frames (Only used for Vision/Legacy)
        self.frame_stack = deque(maxlen=4)

        if SB3_AVAILABLE and model_path and os.path.exists(model_path):
            try:
                self.model = PPO.load(model_path)
                if self.debug: 
                    print(f"[DEBUG] Loaded model from {model_path}")
                    print(f"[DEBUG] Configured for Mode: {self.obs_type}")
            except Exception as e:
                print(f"[ERROR] Could not load model: {e}")
        else:
            print(f"[ERROR] Model path not found or SB3 missing: {model_path}")

    def update(self, dt, game_ref=None):
        """
        Called every frame by the game loop.
        """
        self.debug_step += 1
        
        if not self.model or not game_ref:
            # Safe fallback if model failed to load
            self.car.set_input(0, 0, False)
            return

        # 1. Get current standardized frame/vector
        # Pass the correct obs_type so VisionProcessor gives us the right shape
        current_obs = self.vision.get_observation(self.car, game_ref.track_data, obs_type=self.obs_type)

        # 2. Handle Stacking Logic based on Type
        final_obs = None

        if self.obs_type == "NUMERIC":
            # NUMERIC models (MlpPolicy) do NOT want a stack of 4.
            # They want the single current vector (11,).
            final_obs = current_obs
            
        else:
            # VISION or LEGACY models (CnnPolicy) EXPECT a stack of 4.
            if len(self.frame_stack) == 0:
                # Pre-fill stack on first frame
                for _ in range(4): self.frame_stack.append(current_obs)
            else:
                self.frame_stack.append(current_obs)
            
            # Convert deque to numpy array -> (4, 64, 64, 1) or (4, 64, 64)
            final_obs = np.array(self.frame_stack)
        
        # 3. Predict
        try:
            # Predict returns (Action, State)
            action, _states = self.model.predict(final_obs, deterministic=True)
            
            throttle = 0.0
            steering = 0.0
            
            # --- AUTO-DETECT Action Type ---
            
            # Continuous (Float Array)
            if np.issubdtype(action.dtype, np.floating):
                throttle = float(action[0])
                steering = float(action[1])
                
            # Multi-Discrete (Integer Array: [SteerIdx, GasIdx])
            elif action.shape == (2,):
                steering = float(action[0] - 1) # 0,1,2 -> -1, 0, 1
                throttle = float(action[1] - 1)
                
            # Discrete Legacy (Single Int)
            else:
                act_idx = int(action)
                if act_idx == 0: steering = -1.0
                elif act_idx == 1: steering = 1.0
                elif act_idx == 2: throttle = 1.0
                elif act_idx == 3: throttle = -1.0

            # Optional: Debug Print (Every 60 frames)
            if self.debug and self.debug_step % 60 == 0:
                print(f"[AI] Action: {action} -> Steer: {steering:.2f}, Gas: {throttle:.2f}")

            self.car.set_input(throttle, steering, False)

        except Exception as e:
            if self.debug_step % 60 == 0:
                print(f"[ERROR] Prediction failed: {e}")
                print(f"[DEBUG] Input Shape was: {final_obs.shape if hasattr(final_obs, 'shape') else 'Unknown'}")