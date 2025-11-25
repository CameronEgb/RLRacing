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
    def __init__(self, car, model_path, obs_type="VISION", debug=False):
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
        self.debug_step += 1
        
        if not self.model or not game_ref:
            self.car.set_input(0, 0, False)
            return

        current_obs = self.vision.get_observation(self.car, game_ref.track_data, obs_type=self.obs_type)

        final_obs = None

        if self.obs_type == "NUMERIC":
            final_obs = current_obs  # (11,)

        else:
            # Stack 4 frames
            if len(self.frame_stack) == 0:
                for _ in range(4):
                    self.frame_stack.append(current_obs)
            else:
                self.frame_stack.append(current_obs)

            final_obs = np.array(self.frame_stack)  # (4, 64, 64) or (4, 64, 64, 1)

            # CRITICAL FIX: Auto-correct shape for legacy models
            if final_obs.shape[-1] == 1:
                expected_no_channel = (4, 64, 64)
                expected_with_channel = (4, 64, 64, 1)
                
                # Try to infer what the model actually expects
                model_expected = getattr(self.model.observation_space, 'shape', None)
                
                if model_expected == expected_no_channel:
                    # Legacy model! Remove channel dim
                    final_obs = final_obs.squeeze(-1)  # (4, 64, 64, 1) → (4, 64, 64)
                    if self.debug and self.debug_step % 120 == 0:
                        print("[AI] Legacy model detected → squeezed channel dim")
                elif model_expected == expected_with_channel or model_expected is None:
                    # New model or unknown → keep (4, 64, 64, 1)
                    pass
                else:
                    # Still wrong? Force squeeze as last resort (very common with old models)
                    if final_obs.shape != model_expected:
                        final_obs = final_obs.squeeze(-1)
                        if self.debug:
                            print(f"[AI] Forced squeeze: {final_obs.shape} to match model")

        # Now predict safely
        try:
            action, _ = self.model.predict(final_obs, deterministic=True)
            
            # === Action decoding (unchanged) ===
            throttle = steering = 0.0
            if np.issubdtype(action.dtype, np.floating) and len(action) >= 2:
                throttle = float(action[0])
                steering = float(action[1])
            elif hasattr(action, 'shape') and action.shape == (2,):
                steering = float(action[0] - 1)
                throttle = float(action[1] - 1)
            else:
                act_idx = int(action)
                actions = [(-1,0), (1,0), (0,1), (0,-1), (0,0)]
                if act_idx < len(actions):
                    steering, throttle = actions[act_idx]

            if self.debug and self.debug_step % 60 == 0:
                print(f"[AI] Action → Steer: {steering:+.2f}, Throttle: {throttle:+.2f} | Obs: {final_obs.shape}")

            self.car.set_input(throttle, steering, False)

        except Exception as e:
            if self.debug_step % 60 == 0:
                print(f"[ERROR] Prediction failed: {e}")
                print(f"   Obs shape sent: {final_obs.shape if hasattr(final_obs, 'shape') else type(final_obs)}")
                print(f"   Model expected: {getattr(self.model.observation_space, 'shape', 'Unknown')}")