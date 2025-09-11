# Low-Poly Racing Game

A top-down racing game with procedurally generated tracks, realistic physics, and a chill low-poly aesthetic.

## Features

- **Procedural Track Generation**: Every run features a unique racing circuit generated using Catmull-Rom splines
- **Realistic Car Physics**: Implements proper vehicle dynamics including:
  - Vector-based velocity and acceleration
  - Tire friction with grip limits
  - Weight transfer effects
  - Engine torque curves and RPM simulation
  - Aerodynamic drag and downforce
  - Realistic collision response
- **AI Opponent**: Placeholder AI system ready for expansion
- **Low-Poly Chill Aesthetic**: Clean, minimalist visual design
- **Smooth Camera System**: Predictive camera following with lookahead
- **Visual Effects**: Tire marks, particles, and audio visualization

## Requirements

- Python 3.7+
- Pygame 2.0+

## Installation

1. Install Python 3.7 or higher from [python.org](https://www.python.org/)

2. Install Pygame:
   ```bash
   pip install pygame
   ```

3. Download all game files:
   - `main.py`
   - `track_generator.py` 
   - `car.py`
   - `ux.py`
   - `ai_opponent.py`

## How to Run

1. Open terminal/command prompt in the game directory
2. Run the game:
   ```bash
   python main.py
   ```

## Controls

- **WASD** or **Arrow Keys**: Drive the car
  - W/Up: Accelerate
  - S/Down: Brake/Reverse
  - A/Left: Turn left
  - D/Right: Turn right
- **ESC**: Quit game

## Game Architecture

### Core Modules

1. **main.py**: Entry point, initializes game systems and runs main loop
2. **track_generator.py**: Procedural track generation using mathematical splines
3. **car.py**: Realistic vehicle physics simulation
4. **ux.py**: Camera, rendering, input handling, and UI
5. **ai_opponent.py**: AI opponent controller (currently minimal placeholder)

### Physics Implementation

The car physics system replicates real-world driving behavior:

- **Engine Simulation**: RPM-based torque curves, gear ratios
- **Tire Physics**: Grip limits, slip angles, Pacejka tire model approximation  
- **Aerodynamics**: Drag forces, downforce effects
- **Weight Transfer**: Affects steering during acceleration/braking
- **Surface Friction**: Different grip levels on/off track

### Track Generation Algorithm

1. **Control Points**: Generate random points in circular pattern
2. **Spline Interpolation**: Use Catmull-Rom splines for smooth curves
3. **Boundary Creation**: Calculate perpendicular offsets for track width
4. **Racing Line**: Analyze curvature to determine optimal path
5. **Checkpoints**: Place lap detection points evenly around track

### Rendering System

- **Low-Poly Aesthetic**: Simple polygons, clean lines, muted colors
- **Camera Following**: Smooth tracking with predictive lookahead
- **Visual Effects**: Tire marks, dust particles, audio visualization
- **UI Design**: Semi-transparent panels with performance info

## Customization

### Track Generation
Modify `generate_track()` parameters in `main.py`:
- `width`: Track width (default: 50)
- `complexity`: Number of control points (default: 8)

### Car Properties
Adjust car parameters in `main.py`:
- `max_speed`: Top speed limit
- `acceleration`: Engine power
- `turning_speed`: Steering responsiveness  
- `friction`: Grip level

### Visual Style
Edit color palette in `ux.py`:
```python
self.colors = {
    'grass': (85, 120, 85),
    'track': (70, 70, 80),
    'sky': (120, 140, 160),
    # ... more colors
}
```

## Future Enhancements

The game architecture supports easy expansion:

- **AI Racing**: Implement path following, overtaking, strategic behavior
- **Multiplayer**: Add split-screen or network multiplayer
- **Car Tuning**: Adjustable suspension, aerodynamics, engine mapping
- **Weather Effects**: Rain, wind affecting physics
- **Championship Mode**: Multiple races, points system
- **Sound System**: Engine audio, tire squealing, collision sounds
- **Track Editor**: Visual track creation tools

## Technical Details

### Performance
- Target: 60 FPS
- Optimized rendering with screen culling
- Particle system with automatic cleanup
- Efficient collision detection

### Physics Accuracy
The physics system models real racing concepts:
- Late apex cornering technique
- Trail braking effects
- Understeer/oversteer balance
- Racing line optimization
- Tire temperature simulation (framework in place)

## Troubleshooting

### Common Issues

1. **Game won't start**: Check Python and Pygame versions
2. **Poor performance**: Reduce particle count in `ux.py`
3. **Car feels unresponsive**: Adjust input smoothing in `handle_input()`
4. **Track looks wrong**: Regenerate by restarting (tracks are random)

### Debug Mode

Add debug features by modifying `ux.py`:
```python
self.show_racing_line = True  # Show optimal path
self.debug_physics = True     # Show force vectors
```

## License

This game is provided as-is for educational and entertainment purposes. Feel free to modify and expand upon the codebase.

## Credits

- Procedural generation using Catmull-Rom spline mathematics
- Physics based on real vehicle dynamics principles
- Low-poly aesthetic inspired by modern indie games
- Built with Python and Pygame