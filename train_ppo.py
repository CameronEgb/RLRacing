# train_ppo_ultraquick_batchfix.py
# Fixed batching: Ensure action is at least 1D before step() to satisfy DummyVecEnv
# Still old API, no Gymnasium; caps loops
# Run: python train_ppo_ultraquick_batchfix.py

import os
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecFrameStack, DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback

# Adjust path if necessary
from env_wrapper import RacingEnv

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
    print("Dirs created/verified. Starting ultra-quick batch-fixed run...")

    # Configure (n_envs=4 for debug speed)
    n_envs = 4
    env_fns = [make_env(i, seed=1234) for i in range(n_envs)]
    vec_env = SubprocVecEnv(env_fns)
    vec_env = VecFrameStack(vec_env, n_stack=4)

    # Model (n_epochs=5 for speed)
    model = PPO(
        "CnnPolicy",
        vec_env,
        verbose=1,
        n_steps=2048 // n_envs,
        batch_size=64,
        n_epochs=5,
        learning_rate=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
    )

    # Custom callbacks
    class CustomCheckpointCallback(BaseCallback):
        def __init__(self, save_freq: int, save_path: str, name_prefix: str, verbose=0):
            super(CustomCheckpointCallback, self).__init__(verbose)
            self.save_freq = save_freq
            self.save_path = save_path
            self.name_prefix = name_prefix
            self.last_save = 0
            print(f"CheckpointCB init: save_freq={save_freq}")

        def _on_step(self) -> bool:
            if self.n_calls % 500 == 0 and self.n_calls > 0:
                print(f"CheckpointCB on_step: n_calls={self.n_calls}")
            
            if self.n_calls >= self.last_save + self.save_freq:
                save_path = os.path.join(self.save_path, f"{self.name_prefix}_{self.n_calls}_steps.zip")
                print(f"TRIGGERING SAVE at {self.n_calls} steps: {save_path}")
                try:
                    self.model.save(save_path)
                    print(f"SUCCESS: Saved {save_path}")
                except Exception as e:
                    print(f"ERROR saving: {e}")
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
            self.eval_results = []
            print(f"EvalCB init: eval_freq={eval_freq}, episodes={n_eval_episodes}")

        def _on_step(self) -> bool:
            if self.n_calls % 500 == 0 and self.n_calls > 0:
                print(f"EvalCB on_step: n_calls={self.n_calls}")
            
            if self.n_calls >= self.last_eval + self.eval_freq:
                print(f"TRIGGERING EVAL at {self.n_calls} steps")
                try:
                    episode_rewards, episode_lengths = [], []
                    for ep in range(self.n_eval_episodes):
                        # OLD GYM API: reset returns 1 item (batched)
                        obs = self.eval_env.reset()
                        obs = obs[0] if len(obs.shape) > 0 else obs  # De-batch obs
                        print(f"  Eval reset obs shape: {obs.shape}")
                        done = False
                        ep_reward = 0.0
                        ep_length = 0
                        max_steps = 2000  # Cap to prevent hangs
                        while not done and ep_length < max_steps:
                            action, _ = self.model.predict(obs, deterministic=True)
                            if ep == 0 and ep_length < 5:
                                print(f"  Predict input shape: {obs.shape}, action shape: {action.shape}")
                            # FIXED: Ensure action is at least 1D (for DummyVecEnv)
                            if np.isscalar(action) or len(action.shape) == 0:
                                action = np.atleast_1d(action)
                            if ep_length % 100 == 0 and ep_length > 0:
                                print(f"    Eval step {ep_length}: still running...")
                            # OLD GYM API: step returns 4 items (batched)
                            step_ret = self.eval_env.step(action)
                            obs_batch, reward_batch, done_batch, info = step_ret
                            obs = obs_batch[0] if len(obs_batch.shape) > 0 else obs_batch  # De-batch
                            reward = float(reward_batch[0]) if len(reward_batch.shape) > 0 else float(reward_batch)
                            done = bool(done_batch[0]) if len(done_batch.shape) > 0 else bool(done_batch)  # De-batch done
                            ep_reward += reward
                            ep_length += 1
                            if ep_length >= max_steps:
                                print(f"  WARNING: Episode {ep+1} capped at {max_steps} steps")
                                done = True
                        episode_rewards.append(ep_reward)
                        episode_lengths.append(ep_length)
                        print(f"  Episode {ep+1}: reward={ep_reward:.2f}, length={ep_length}")
                    
                    mean_reward = np.mean(episode_rewards)
                    mean_length = np.mean(episode_lengths)
                    self.eval_results.append((self.n_calls, mean_reward, mean_length))
                    print(f"EVAL COMPLETE: mean_reward={mean_reward:.2f}, mean_length={mean_length:.1f}")
                    
                    # Save NPZ
                    np.savez(os.path.join(self.log_path, f"evaluations_{self.n_calls}.npz"),
                             timesteps=self.n_calls, results=np.array(self.eval_results))
                    print(f"SUCCESS: Eval log saved")
                except Exception as e:
                    print(f"ERROR in eval: {e}")
                    import traceback
                    traceback.print_exc()
                self.last_eval = self.n_calls
            return True

    # Eval env
    eval_env_fn = make_eval_env()
    eval_env = DummyVecEnv([eval_env_fn])
    eval_env = VecFrameStack(eval_env, n_stack=4)
    print(f"Eval env ready: obs_space={eval_env.observation_space}, action_space={eval_env.action_space}")

    # Init callbacks
    checkpoint_cb = CustomCheckpointCallback(save_freq=2_000, save_path="./models/", name_prefix="ppo_race_ultraquick_batchfix")
    eval_cb = CustomEvalCallback(eval_env, eval_freq=2_000, log_path="./logs/", n_eval_episodes=1)

    print("Callbacks attached. Starting learn...")
    model.learn(total_timesteps=8_000, callback=[checkpoint_cb, eval_cb])
    
    # Final save
    model.save("models/ppo_example.zip")
    vec_env.close()
    eval_env.close()
    print("Ultra-quick batchfix run complete! Check for eval completion and files.")