# train_ppo_master.py
# Trains an agent on a specific, persistent "Master Track"
# Includes Logging, Checkpoints, and Evaluation.

import os
import shutil
import time
os.environ["IS_TRAINING"] = "true"

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback, CallbackList
import gymnasium as gym

from env_wrapper import RacingEnv
from game.track_generator import generate_track
from game.track_storer import save_track, load_track

# ========================================================
# CONFIGURATION
# ========================================================

# 1. Choose Observation Space: "VISION" or "NUMERIC"
# VISION:  Uses CNN. Slower training, "cool factor", learns from pixels.
# NUMERIC: Uses MLP (Rays/Sensors). Extremely fast training, usually higher performance.
# ACTION_TYPE: "continuous or multi-discrete"
# "continuous": Agent outputs specific floats [-1.0 to 1.0]
OBSERVATION_TYPE = "NUMERIC" 
ACTION_TYPE = "continuous"
COMPLEXITY = 16
WIDTH = 70
WEATHER = "RAIN"   #["CLEAR", "RAIN", "SNOW"]

REMAKETRACK = True
TRACK_NAME = f"{WEATHER}-W{WIDTH}-C{COMPLEXITY}"

# - 24 - 80  - get teh right track
# - 16 - 70 
# - 8 -  60


LOG_DIR = f"./logs/{TRACK_NAME}_{OBSERVATION_TYPE}/"
MODELS_DIR = f"./models/{TRACK_NAME}_{OBSERVATION_TYPE}/"

if os.path.exists(MODELS_DIR) and REMAKETRACK:
    print("Regenerating track... Removing old models and logs")
    shutil.rmtree(MODELS_DIR)
    shutil.rmtree(LOG_DIR)

os.makedirs(LOG_DIR, exist_ok=True) 
os.makedirs(MODELS_DIR, exist_ok=True)

# --------------------------------------------------------
# 1. Ensure Master Track Exists
# --------------------------------------------------------
TRACK_FILE = f"tracks/{TRACK_NAME}.json"
existing_track = load_track(TRACK_FILE)

if existing_track is None or REMAKETRACK:
    if not REMAKETRACK:
        print(f"Track {TRACK_NAME} not found. Generating new one...")
    else: print(f"Regenerating track {TRACK_NAME}...")
    new_track = generate_track(width=WIDTH, complexity=COMPLEXITY, intended_weather=WEATHER)#, seed=12345)
    save_track(new_track, TRACK_FILE)
    master_track = new_track
else:
    print("Loaded existing master track.")
    master_track = existing_track

# --------------------------------------------------------
# 2. Setup Environment
# --------------------------------------------------------

def make_env():
    # Note: You must update your RacingEnv.__init__ to accept 'obs_type'
    # and set the self.observation_space accordingly!
    # If VISION: Box(0, 255, (64, 64, 1), uint8)
    # If NUMERIC: Box(-inf, inf, (N_SENSORS,), float32)
    env = RacingEnv(
        screen_size=(640, 640),
        obs_size=(64, 64),
        track_data=master_track,
        action_type=ACTION_TYPE,
        obs_type=OBSERVATION_TYPE # <--- Passing the flag to the Env
    )
    env = Monitor(env, LOG_DIR) 
    return env

# Create Vectorized Environment
vec_env = DummyVecEnv([make_env for _ in range(1)])

# Only stack frames if using Vision. 
# For Numeric (Lidar), stacking is optional but often instantaneous velocity is enough.
if OBSERVATION_TYPE == "VISION":
    vec_env = VecFrameStack(vec_env, n_stack=4)

# Evaluation Env
eval_env = DummyVecEnv([make_env for _ in range(1)])
if OBSERVATION_TYPE == "VISION":
    eval_env = VecFrameStack(eval_env, n_stack=4)

# --------------------------------------------------------
# 3. Setup Callbacks
# --------------------------------------------------------

checkpoint_callback = CheckpointCallback(
    save_freq=1_000_000,
    save_path=MODELS_DIR,
    name_prefix=f"ppo_{OBSERVATION_TYPE.lower()}"
)

eval_callback = EvalCallback(
    eval_env,
    best_model_save_path=f"{MODELS_DIR}/best_model",
    log_path=LOG_DIR,
    eval_freq=10_000,
    deterministic=True,
    render=False,
    n_eval_episodes=5
)

callbacks = CallbackList([checkpoint_callback, eval_callback])

# --------------------------------------------------------
# 4. Setup Model & Network Architecture
# --------------------------------------------------------

# Select Policy based on Observation Type
if OBSERVATION_TYPE == "VISION":
    policy_type = "CnnPolicy"
    # Vision needs a deeper dense head after the CNN extracts features
    policy_kwargs = dict(
        net_arch=dict(pi=[256, 256], vf=[256, 256])
    )
    # Vision needs a larger buffer to gather enough diverse images
    n_steps_config = 2048
    
elif OBSERVATION_TYPE == "NUMERIC":
    policy_type = "MlpPolicy"
    # Numeric (Lidar) is simple, standard dense network is fine
    policy_kwargs = dict(
        net_arch=dict(pi=[256, 256], vf=[256, 256])
    )
    # Numeric can train with smaller buffers if needed, but 2048 is stable
    n_steps_config = 2048

model = PPO(
    policy_type,
    vec_env,
    policy_kwargs=policy_kwargs,
    verbose=1,
    learning_rate=3e-4,
    n_steps=n_steps_config,
    batch_size=64,
    gamma=0.99,
    gae_lambda=0.95,
    ent_coef=0.01,
    tensorboard_log=LOG_DIR
)

# --------------------------------------------------------
# 5. Train
# --------------------------------------------------------
print(f"Starting training with [{OBSERVATION_TYPE}] observation space...")
print(f"Policy Type: {policy_type}")
print(f"Logs: {LOG_DIR}")

model.learn(total_timesteps=10_000_000, callback=callbacks)

final_model_name = f"{MODELS_DIR}/ppo_final"
model.save(final_model_name)
print(f"Training Complete. Saved to {final_model_name}")