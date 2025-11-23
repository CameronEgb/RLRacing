# train_ppo_master.py
# Trains an agent on a specific, persistent "Master Track"
# This allows the agent to overfit/master one specific course.

import os
import time
os.environ["IS_TRAINING"] = "true"

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack
from stable_baselines3.common.callbacks import BaseCallback
import gymnasium as gym

from ai.env_wrapper import RacingEnv
from game.track_generator import generate_track
from game.track_storer import save_track, load_track

# --------------------------------------------------------
# 1. Ensure Master Track Exists
# --------------------------------------------------------
TRACK_FILE = "tracks/master_track.json"
existing_track = load_track(TRACK_FILE)

if existing_track is None:
    print("No master track found. Generating new one...")
    # Generate a complex track for the champion to learn
    new_track = generate_track(width=55, complexity=14, seed=12345)
    save_track(new_track, TRACK_FILE)
    master_track = new_track
else:
    print("Loaded existing master track.")
    master_track = existing_track

# --------------------------------------------------------
# 2. Setup Environment
# --------------------------------------------------------

def make_env():
    # Pass the LOADED track to the env
    env = RacingEnv(
        screen_size=(640, 640),
        obs_size=(64, 64),
        track_data=master_track  # Force this track
    )
    return env

# Use DummyVecEnv to avoid Pygame Multiprocessing issues
vec_env = DummyVecEnv([make_env for _ in range(1)])
vec_env = VecFrameStack(vec_env, n_stack=4)

# --------------------------------------------------------
# 3. Setup Model
# --------------------------------------------------------
policy_kwargs = dict(
    features_extractor_kwargs=dict(normalized_image=False)
)

model = PPO(
    "CnnPolicy",
    vec_env,
    policy_kwargs=policy_kwargs,
    verbose=1,
    learning_rate=3e-4,
    n_steps=1024,
    batch_size=64,
    gamma=0.99,
    ent_coef=0.01,
)

# --------------------------------------------------------
# 4. Train
# --------------------------------------------------------
print("Starting training on Master Track...")
# Train for enough steps to master the track (e.g., 100k)
model.learn(total_timesteps=100_000)

model_name = "models/ppo_champion"
model.save(model_name)
print(f"Champion model saved to {model_name}")