# Reinforced Racing: Low-Poly Racing Game with RL Opponents

A top-down racing game with procedurally generated tracks, realistic physics, a chill low-poly aesthetic, and reinforcement learning (RL) for AI opponents. Built for testing RL in dynamic environments, inspired by Mario Kart-style racing with tunable difficulty.

## Quick Start: RL Training and Testing

To train and test the PPO-based RL agent for the AI opponent:

### Requirements (RL-Specific)
In addition to base requirements, install RL libraries:
```bash
pip install stable-baselines3 gymnasium torch  # PPO + env wrapper
```

### Training the Agent
1. Ensure `IS_TRAINING=true` in your environment (or set via `os.environ` in scripts).
2. Run the quick training script for a short test (4k steps, ~10 min):
   ```bash
   python train_ppo_quick.py
   ```
   - Outputs checkpoints to `./models/` (e.g., `ppo_race_quick_custom_500_steps.zip`).
   - Eval logs to `./logs/` (e.g., `evaluations_500.npz` with mean rewards/lengths).

3. For full training (e.g., 200k+ steps, ~1-2 hours on CPU; faster on GPU):
   - Edit `train_ppo_quick.py`: Set `total_timesteps=200000`, `save_freq=5000`, `eval_freq=5000`.
   - Run: `python train_ppo_quick.py`.
   - Monitor verbose output for rewards (target: >100 normalized returns) and losses.

### Testing the Agent
1. Load a trained model in-game:
   - Edit `main.py`: Uncomment `ChosenAIOpponent = AIOpponent` (default is random baseline).
   - Set `model_path` in `ai_opponent.py` to your checkpoint (e.g., `"models/ppo_race_quick_custom_200000_steps.zip"`).

2. Run the game:
   ```bash
   python main.py
   ```
   - Race against the RL AI on procedural tracks (complexity 6-24 via arrows in menu).
   - Use `R` to reset positions; `N` for new track.

3. Standalone Eval (from training script):
   - After training, load the final model: `model = PPO.load("models/ppo_race_quick_final.zip")`.
   - Run evals manually via `CustomEvalCallback` for metrics like mean reward/length.

**Tips**: 
- Tracks randomize on reset for domain adaptation.
- Debug: Set `render_mode='human'` in `RacingEnv` for visual training (slower).
- Compare baselines: Toggle to `RandomAIOpponent` in `main.py`.

For full reproducibility, see [GitHub Repo](https://github.com/CameronEgb/RLRacing).

## Features

- **Procedural Track Generation**: Unique circuits via Catmull-Rom splines, tunable width/complexity.
- **Realistic Car Physics**: Vector velocity, tire friction (Pacejka approx.), weight transfer, torque curves, drag/downforce, collisions.
- **RL-Powered AI Opponent**: PPO agent (Stable Baselines3) learns from pixel obs; outperforms random on straights, tunable skill.
- **Low-Poly Chill Aesthetic**: Minimalist polygons, muted colors, smooth camera with lookahead.
- **Visual Effects**: Tire marks, particles, UI overlays (lap times, speeds).
- **Game Modes**: Menu for settings; race with resets/new tracks.

## Base Requirements

- Python 3.10+
- Pygame 2.0+

## Full Installation

1. Install Python 3.10+ from [python.org](https://www.python.org/).

2. Install dependencies:
   ```bash
   pip install pygame stable-baselines3 gymnasium torch numpy  # Base + RL
   ```

3. Clone/Download files:
   - Core: `main.py`, `track_generator.py`, `car.py`, `ux.py`.
   - RL: `ai_opponent.py`, `env_wrapper.py`, `train_ppo_quick.py`, `random_ai_opponent.py`.

## Running the Base Game

1. In the project directory:
   ```bash
   python main.py
   ```

## Controls

- **WASD/Arrows**: Drive (W: accel, S: brake, A/D: steer).
- **Space**: Handbrake (bonus grip).
- **ESC**: Menu/Quit.
- **R**: Reset cars (in race).
- **N**: New track with pending settings.
- **Arrows (Menu)**: Adjust pending width (Up/Down) / complexity (Left/Right).
- **Enter**: Start race.

## Game Architecture

### Core Modules

1. **main.py**: Main loop, state management (menu/race), input/UI.
2. **track_generator.py**: Spline-based track gen with racing lines/checkpoints.
3. **car.py**: Physics sim (velocity, forces, collisions).
4. **ux.py**: Rendering, camera, effects, debug overlays.
5. **ai_opponent.py**: RL inference (PPO on stacked grayscale frames).
6. **env_wrapper.py**: Gymnasium env for training (pixel obs, discrete actions).
7. **train_ppo_quick.py**: PPO training with vec envs, callbacks.
8. **random_ai_opponent.py**: Simple baseline for comparison.

### Physics Implementation

- **Engine**: RPM-torque curves, gears.
- **Tires**: Slip angles, friction variants (on/off-track).
- **Dynamics**: Under/oversteer, trail braking, weight shift.
- **RL Integration**: Syncs car state to env for real-time pixel-based actions.

### Track Generation

1. Random control points in loop.
2. Catmull-Rom splines for centerline.
3. Perp offsets for boundaries.
4. Curvature-based racing line.
5. Procedural variety: Width (30-80), complexity (6-24 points).

### Rendering

- Top-down view, 1200x800 window.
- Low-poly: Simple polys, gradients.
- Effects: Particles, marks; 60 FPS target.

## Customization

### Track Params (in `main.py`)
```python
track = generate_track(width=50, complexity=10)
```

### Car Tuning (in `car.py`)
```python
self.max_speed = 200  # px/s
self.acceleration = 5.0
self.friction = 0.8
```

### RL Params (in `train_ppo_quick.py`)
```python
model = PPO("CnnPolicy", vec_env, learning_rate=3e-4, n_steps=512//8)
```

### Visuals (in `ux.py`)
```python
self.colors = {'grass': (85, 120, 85), 'track': (70, 70, 80)}
```

## RL Evaluation & Metrics

- **Training Logs**: Verbose PPO output (rewards, losses); check `./logs/` for NPZ evals.
- **Key Metrics**: Episode reward (progress - penalties), length (sustained driving), velocity (px/s).
- **Baselines**: Random AI (uniform actions); human play.
- **Pilot Results**: At 1.7M steps, rewards ~45 (up from -20); stable policy but high value loss (50)—needs longer runs.
- **Debug**: Enable `show_racing_line=True` in `ux.py`; monitor stuck timers in AI.

## Future Enhancements

- **Advanced RL**: Curriculum learning, hybrid states (pixels + vectors), multi-agent.
- **Modes**: Grand Prix (pre-gen tracks), Arcade (endless scoring).
- **AI Scaling**: Difficulty via entropy/noise; overtake logic.
- **Extras**: Multiplayer, weather, car variants, sound, track editor.
- **Research**: Ablate rewards for optimal lines (RQ3); benchmark vs. humans (RQ2).

## Technical Details

- **Performance**: 60 FPS; vec envs for parallel training (8 envs).
- **RL Setup**: Discrete(5) actions; grayscale CNN obs (64x64x6 stack); domain randomization via proc tracks.
- **Physics Accuracy**: Supports late-apex, grip limits; RL learns straights but struggles on turns.

## Troubleshooting

- **Training Crashes**: Set `SDL_VIDEODRIVER=dummy`; check env seed.
- **Slow Inference**: Use deterministic predict; reduce frame stack.
- **No Model Load**: Verify path in `ai_opponent.py`; train first.
- **Pygame Issues**: Update SDL; test headless.
- **Debug**: Add `print` in `update()`; visualize obs in env.

## License & Credits

MIT License for educational use. Credits: Catmull-Rom math, Stable Baselines3 for PPO, Pygame for rendering. Authors: Kevin Alvarenga, Cameron Egbert (NCSU).