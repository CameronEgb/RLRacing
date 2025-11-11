# train_ppo_quick.py
# Even quicker test: total_timesteps=20_000 (~10-min run at your rate)
# save_freq=5_000 and eval_freq=5_000 to trigger callbacks super early
# n_eval_episodes=1 for faster evals
# Still fixes eval_env mismatch
# Run: python train_ppo_quick.py
# Expect: Checkpoints in ./models/ every 5k steps (~2.5 mins first); eval logs in ./logs/ every 5k

import os
os.environ["IS_TRAINING"] = "true"  # Enables headless mode for training

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecFrameStack, DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
import gymnasium as gym
import numpy as np

# Adjust path if necessary
from env_wrapper import RacingEnv

# Custom callback to force checkpoints and evals (bypasses SB3 bugs)
from stable_baselines3.common.callbacks import BaseCallback

class CustomCheckpointCallback(BaseCallback):
    def __init__(self, save_freq: int, save_path: str, name_prefix: str, verbose=0):
        super(CustomCheckpointCallback, self).__init__(verbose)
        self.save_freq = save_freq
        self.save_path = save_path
        self.name_prefix = name_prefix
        self.last_save = 0

    def _on_step(self) -> bool:
        if self.n_calls >= self.last_save + self.save_freq:
            save_path = os.path.join(self.save_path, f"{self.name_prefix}_{self.n_calls}_steps.zip")
            self.model.save(save_path)
            print(f"Custom save at {self.n_calls} steps: {save_path}")
            self.last_save = self.n_calls
        return True

class CustomEvalCallback(BaseCallback):
    def __init__(self, eval_env, eval_freq: int, log_path: str, n_eval_episodes: int, verbose=0):
        super(CustomEvalCallback, self).__init__(verbose)
        self.eval_env = eval_env
        self.eval_freq = eval_freq
        self.log_path = log_path
        self.n_eval_episodes = n_eval_episodes
        self.last_eval = 0
        import numpy as np  # For logging
        self.eval_results = []  # Simple list to track

    def _on_step(self) -> bool:
        if self.n_calls >= self.last_eval + self.eval_freq:
            # Run eval (handle VecEnv batching, even for n_envs=1)
            episode_rewards, episode_lengths = [], []
            for _ in range(self.n_eval_episodes):
                obs = self.eval_env.reset()  # Shape: (1, 64,64,6)
                episode_reward = 0
                episode_length = 0
                done = np.array([False])  # Shape: (1,)
                while not done.any():
                    action, _ = self.model.predict(obs, deterministic=True)
                    obs, rewards, dones, _, infos = self.eval_env.step(action)
                    episode_reward += rewards[0]  # Single env index 0
                    episode_length += 1
                    done = dones
                episode_rewards.append(episode_reward)
                episode_lengths.append(episode_length)
            mean_reward = np.mean(episode_rewards)
            mean_length = np.mean(episode_lengths)
            self.eval_results.append((self.n_calls, mean_reward, mean_length))
            print(f"Custom eval at {self.n_calls} steps: mean_reward={mean_reward:.2f}, mean_length={mean_length:.1f}")
            
            # Save simple NPZ log (mimics EvalCallback)
            np.savez(os.path.join(self.log_path, f"evaluations_{self.n_calls}.npz"),
                     timesteps=self.n_calls, results=np.array(self.eval_results))
            print(f"Eval log saved: evaluations_{self.n_calls}.npz")
            self.last_eval = self.n_calls
        return True


def make_env(rank=0, seed=0):
    def _init():
        env = RacingEnv(
            screen_size=(640, 640),
            obs_size=(64, 64),
            action_repeat=2,
            max_episode_seconds=45.0,
            render_mode=None,
            track_kwargs={}
        )
        env.seed(seed + rank)
        return env
    return _init

def make_eval_env(seed=1234):
    def _init():
        env = RacingEnv(
            screen_size=(640, 640),
            obs_size=(64, 64),
            action_repeat=2,
            max_episode_seconds=45.0,
            render_mode=None,
            track_kwargs={}
        )
        env.seed(seed)
        return env
    return _init

if __name__ == "__main__":
    # Create dirs if missing
    os.makedirs("./models", exist_ok=True)
    os.makedirs("./logs", exist_ok=True)

    # Configure multiprocessing (keep 8 for speed)
    n_envs = 8
    env_fns = [make_env(i, seed=1234) for i in range(n_envs)]
    vec_env = SubprocVecEnv(env_fns)

    # Frame stack (align with inference: 6)
    vec_env = VecFrameStack(vec_env, n_stack=6)

    # Policy kwargs for grayscale stack (disable norm/transpose for C=6; use 'normalized_image' for compat)
    policy_kwargs = dict(
        features_extractor_kwargs=dict(normalized_image=False)
    )

    # Create model (same as original, + policy_kwargs)
    model = PPO(
        "CnnPolicy",
        vec_env,
        policy_kwargs=policy_kwargs,
        verbose=1,
        n_steps=512 // n_envs,
        batch_size=64,
        n_epochs=10,
        learning_rate=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
    )

    # Usage (replace old callbacks)
    checkpoint_cb = CustomCheckpointCallback(save_freq=50_000, save_path="./models/", name_prefix="ppo_race_quick_custom")
    eval_env_fn = DummyVecEnv([make_eval_env()])
    eval_env = VecFrameStack(eval_env_fn, n_stack=6)  # Align stacking
    eval_cb = CustomEvalCallback(eval_env, eval_freq=50_000, log_path="./logs/", n_eval_episodes=1)

    # Train with them (uncomment eval_cb if desired; quick run uses checkpoint only)
    model.learn(total_timesteps=3_000_000, callback=[checkpoint_cb])#, eval_cb])
    model.save("models/ppo_race_quick_final.zip")
    vec_env.close()
    eval_env.close()
    print("Quick run complete! Check ./models/ for checkpoints (e.g., ppo_race_quick_X_steps.zip) and ./logs/ for evaluations.npz")