import pygame
import math
import random
from typing import Dict, List, Tuple
from car import Car

class GameUX:
    """
    Handles camera, rendering, input, and UI for the racing game.
    Implements low-poly chill aesthetic with smooth camera following.
    """
    
    def __init__(self, screen: pygame.Surface, track_data: Dict, player_car: Car, ai_car: Car):
        self.screen = screen
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()
        
        self.track_data = track_data
        self.player_car = player_car
        self.ai_car = ai_car
        
        # Camera system for smooth following
        self.camera_x = player_car.x
        self.camera_y = player_car.y
        self.camera_smoothing = 0.05  # Lower = smoother, higher = more responsive
        self.camera_lookahead = 80    # Camera looks ahead in driving direction
        
        # Low-poly chill color palette
        self.colors = {
            'grass': (85, 120, 85),           # Muted green
            'track': (70, 70, 80),            # Cool gray
            'track_lines': (90, 90, 100),     # Lighter gray
            'barriers': (60, 60, 70),         # Dark gray
            'ui_bg': (40, 45, 50),            # Dark blue-gray
            'ui_text': (200, 210, 220),       # Light gray
            'sky': (120, 140, 160),           # Soft blue
            'checkpoint': (255, 200, 100),    # Warm yellow
            'racing_line': (100, 200, 255)   # Bright blue
        }
        
        # UI font
        pygame.font.init()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        
        # Input states
        self.keys_pressed = set()
        
        # Visual effects
        self.tire_marks = []  # Store tire mark positions
        self.particles = []   # Dust/debris particles
        
        # Audio simulation (visual feedback)
        self.engine_volume_visual = 0.0
        self.tire_squeal_visual = 0.0
        
        # Performance monitoring
        self.frame_count = 0
        self.fps_counter = 0
        self.last_fps_time = pygame.time.get_ticks()
    
    def handle_input(self):
        """
        Handle keyboard input with natural WASD/Arrow key mapping.
        Implements realistic input curves for smooth control.
        """
        keys = pygame.key.get_pressed()
        
        # Throttle control (W/Up = accelerate, S/Down = brake/reverse)
        throttle = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            throttle = 1.0
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            throttle = -1.0  # Braking/reverse
        
        # Steering control (A/Left = left, D/Right = right)  
        steering = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            steering = -1.0  # Turn left
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            steering = 1.0   # Turn right
        
        # Apply input smoothing for more realistic control
        # Real cars don't instantly respond to input
        current_throttle = getattr(self.player_car, 'smooth_throttle', 0.0)
        current_steering = getattr(self.player_car, 'smooth_steering', 0.0)
        
        # Smooth input transitions (simulates realistic pedal/wheel response)
        input_smoothing = 0.15
        self.player_car.smooth_throttle = current_throttle + (throttle - current_throttle) * input_smoothing
        self.player_car.smooth_steering = current_steering + (steering - current_steering) * input_smoothing
        
        # Apply to car
        self.player_car.set_input(self.player_car.smooth_throttle, self.player_car.smooth_steering)
    
    def update_camera(self):
        """
        Smooth camera following with predictive lookahead.
        Camera anticipates where the car is going, not just where it is.
        """
        # Calculate target camera position with lookahead
        lookahead_x = math.cos(self.player_car.angle) * self.camera_lookahead
        lookahead_y = math.sin(self.player_car.angle) * self.camera_lookahead
        
        target_x = self.player_car.x + lookahead_x
        target_y = self.player_car.y + lookahead_y
        
        # Smooth camera movement (prevents jarring camera jumps)
        self.camera_x += (target_x - self.camera_x) * self.camera_smoothing
        self.camera_y += (target_y - self.camera_y) * self.camera_smoothing
    
    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        screen_x = int(world_x - self.camera_x + self.screen_width / 2)
        screen_y = int(world_y - self.camera_y + self.screen_height / 2)
        return screen_x, screen_y
    
    def render(self):
        """
        Main rendering function with low-poly chill aesthetic.
        Renders in order: background -> track -> cars -> UI -> effects
        """
        # Update camera position
        self.update_camera()
        
        # Clear screen with sky color
        self.screen.fill(self.colors['sky'])
        
        # Render background grass with subtle pattern
        self._render_background()
        
        # Render track
        self._render_track()
        
        # Render racing line (for reference)
        if hasattr(self, 'show_racing_line') and self.show_racing_line:
            self._render_racing_line()
        
        # Render tire marks for visual feedback
        self._render_tire_marks()
        
        # Render checkpoints
        self._render_checkpoints()
        
        # Render cars
        self._render_car(self.ai_car)
        self._render_car(self.player_car)
        
        # Render particles (dust, debris)
        self._render_particles()
        
        # Render UI
        self._render_ui()
        
        # Update visual effects
        self._update_visual_effects()
        
        # Update performance counters
        self._update_fps()
    
    def _render_background(self):
        """Render background with subtle texture for depth."""
        # Create a subtle grass texture using random dots
        grass_color = self.colors['grass']
        
        for _ in range(50):  # Sparse texture for performance
            x = random.randint(0, self.screen_width)
            y = random.randint(0, self.screen_height)
            
            # Vary grass color slightly for texture
            color_variation = random.randint(-10, 10)
            texture_color = (
                max(0, min(255, grass_color[0] + color_variation)),
                max(0, min(255, grass_color[1] + color_variation)),
                max(0, min(255, grass_color[2] + color_variation))
            )
            
            pygame.draw.circle(self.screen, texture_color, (x, y), 1)
    
    def _render_track(self):
        """
        Render track with low-poly aesthetic.
        Uses simple polygons and clean lines for chill vibe.
        """
        # Render main track surface
        if len(self.track_data['outer_boundary']) > 2 and len(self.track_data['inner_boundary']) > 2:
            # Convert track boundaries to screen coordinates
            outer_screen = [self.world_to_screen(x, y) for x, y in self.track_data['outer_boundary']]
            inner_screen = [self.world_to_screen(x, y) for x, y in self.track_data['inner_boundary']]
            
            # Render track surface (outer boundary)
            if len(outer_screen) > 2:
                pygame.draw.polygon(self.screen, self.colors['track'], outer_screen)
            
            # Cut out inner area (grass in middle)
            if len(inner_screen) > 2:
                pygame.draw.polygon(self.screen, self.colors['grass'], inner_screen)
            
            # Render track boundaries
            if len(outer_screen) > 1:
                pygame.draw.lines(self.screen, self.colors['barriers'], True, outer_screen, 3)
            if len(inner_screen) > 1:
                pygame.draw.lines(self.screen, self.colors['barriers'], True, inner_screen, 3)
        
        # Render centerline for reference
        if len(self.track_data['centerline']) > 1:
            center_screen = [self.world_to_screen(x, y) for x, y in self.track_data['centerline']]
            
            # Dashed centerline
            for i in range(0, len(center_screen) - 1, 4):
                if i + 1 < len(center_screen):
                    pygame.draw.line(self.screen, self.colors['track_lines'], 
                                   center_screen[i], center_screen[i + 1], 2)
    
    def _render_racing_line(self):
        """Render optimal racing line for learning purposes."""
        if len(self.track_data['racing_line']) > 1:
            racing_screen = [self.world_to_screen(x, y) for x, y in self.track_data['racing_line']]
            
            # Render as dotted line
            for i in range(0, len(racing_screen) - 1, 3):
                if i + 1 < len(racing_screen):
                    pygame.draw.line(self.screen, self.colors['racing_line'],
                                   racing_screen[i], racing_screen[i + 1], 1)
    
    def _render_car(self, car: Car):
        """
        Render car with low-poly style and realistic visual feedback.
        Shows tire marks, body lean, and performance indicators.
        """
        # Get car corners in world space
        corners = car.get_corners()
        screen_corners = [self.world_to_screen(x, y) for x, y in corners]
        
        # Render car body
        if len(screen_corners) == 4:
            pygame.draw.polygon(self.screen, car.color, screen_corners)
            
            # Car outline for definition
            pygame.draw.polygon(self.screen, (0, 0, 0), screen_corners, 2)
            
            # Render direction indicator (front of car)
            front_center_x = (screen_corners[2][0] + screen_corners[3][0]) / 2
            front_center_y = (screen_corners[2][1] + screen_corners[3][1]) / 2
            
            # Direction line
            direction_length = 15
            end_x = front_center_x + math.cos(car.angle) * direction_length
            end_y = front_center_y + math.sin(car.angle) * direction_length
            
            pygame.draw.line(self.screen, (255, 255, 255), 
                           (int(front_center_x), int(front_center_y)),
                           (int(end_x), int(end_y)), 3)
        
        # Render car name
        screen_x, screen_y = self.world_to_screen(car.x, car.y - 25)
        name_surface = self.small_font.render(car.name, True, self.colors['ui_text'])
        name_rect = name_surface.get_rect(center=(screen_x, screen_y))
        self.screen.blit(name_surface, name_rect)
        
        # Add tire marks if car is sliding
        if car.tire_squeal_intensity > 0.3:
            self._add_tire_mark(car.x, car.y, car.tire_squeal_intensity)
    
    def _add_tire_mark(self, x: float, y: float, intensity: float):
        """Add tire marks for visual feedback."""
        # Limit number of tire marks for performance
        if len(self.tire_marks) > 200:
            self.tire_marks.pop(0)
        
        # Add new tire mark
        alpha = min(255, int(intensity * 100))
        self.tire_marks.append({
            'x': x,
            'y': y,
            'alpha': alpha,
            'age': 0
        })
    
    def _render_tire_marks(self):
        """Render tire marks with fade-out effect."""
        marks_to_remove = []
        
        for i, mark in enumerate(self.tire_marks):
            screen_x, screen_y = self.world_to_screen(mark['x'], mark['y'])
            
            # Fade tire marks over time
            mark['age'] += 1
            fade_alpha = max(0, mark['alpha'] - mark['age'])
            
            if fade_alpha > 0:
                # Create surface for alpha blending
                mark_surface = pygame.Surface((4, 4))
                mark_surface.fill((40, 40, 40))
                mark_surface.set_alpha(fade_alpha)
                
                self.screen.blit(mark_surface, (screen_x - 2, screen_y - 2))
            else:
                marks_to_remove.append(i)
        
        # Remove faded marks
        for i in reversed(marks_to_remove):
            self.tire_marks.pop(i)
    
    def _render_checkpoints(self):
        """Render checkpoints for lap detection."""
        for checkpoint in self.track_data['checkpoints']:
            screen_x, screen_y = self.world_to_screen(checkpoint['position'][0], 
                                                    checkpoint['position'][1])
            
            # Render checkpoint as a subtle indicator
            color = self.colors['checkpoint'] if not checkpoint['passed'] else (100, 100, 100)
            pygame.draw.circle(self.screen, color, (screen_x, screen_y), 8, 2)
            
            # Checkpoint number
            number_surface = self.small_font.render(str(checkpoint['index']), True, color)
            number_rect = number_surface.get_rect(center=(screen_x, screen_y))
            self.screen.blit(number_surface, number_rect)
    
    def _render_particles(self):
        """Render dust and debris particles for atmosphere."""
        particles_to_remove = []
        
        for i, particle in enumerate(self.particles):
            particle['x'] += particle['vel_x']
            particle['y'] += particle['vel_y']
            particle['life'] -= 1
            
            if particle['life'] > 0:
                screen_x, screen_y = self.world_to_screen(particle['x'], particle['y'])
                
                alpha = (particle['life'] / particle['max_life']) * 100
                particle_surface = pygame.Surface((2, 2))
                particle_surface.fill(particle['color'])
                particle_surface.set_alpha(alpha)
                
                self.screen.blit(particle_surface, (screen_x, screen_y))
            else:
                particles_to_remove.append(i)
        
        # Remove expired particles
        for i in reversed(particles_to_remove):
            self.particles.pop(i)
    
    def _render_ui(self):
        """
        Render game UI with chill aesthetic.
        Shows speed, RPM, lap info, and audio visualization.
        """
        # UI background panel
        ui_rect = pygame.Rect(10, 10, 250, 120)
        ui_surface = pygame.Surface((ui_rect.width, ui_rect.height))
        ui_surface.fill(self.colors['ui_bg'])
        ui_surface.set_alpha(180)  # Semi-transparent
        self.screen.blit(ui_surface, ui_rect)
        
        # Speed display
        speed_kmh = self.player_car.get_speed_kmh()
        speed_text = f"Speed: {speed_kmh:.0f} km/h"
        speed_surface = self.font.render(speed_text, True, self.colors['ui_text'])
        self.screen.blit(speed_surface, (20, 20))
        
        # RPM display
        rpm = self.player_car.get_rpm()
        rpm_text = f"RPM: {rpm}"
        rpm_surface = self.font.render(rpm_text, True, self.colors['ui_text'])
        self.screen.blit(rpm_surface, (20, 45))
        
        # Engine audio visualization (simulated)
        engine_volume = self.player_car.engine_sound_pitch
        audio_text = f"Engine: {'█' * int(engine_volume * 5)}"
        audio_surface = self.font.render(audio_text, True, self.colors['ui_text'])
        self.screen.blit(audio_surface, (20, 70))
        
        # Tire squeal visualization
        squeal = self.player_car.tire_squeal_intensity
        squeal_text = f"Tires: {'█' * int(squeal * 5)}"
        squeal_surface = self.font.render(squeal_text, True, self.colors['ui_text'])
        self.screen.blit(squeal_surface, (20, 95))
        
        # FPS counter
        fps_text = f"FPS: {self.fps_counter}"
        fps_surface = self.small_font.render(fps_text, True, self.colors['ui_text'])
        self.screen.blit(fps_surface, (self.screen_width - 80, 10))
        
        # Controls hint
        controls_y = self.screen_height - 60
        controls = [
            "WASD / Arrow Keys: Drive",
            "ESC: Quit"
        ]
        
        for i, control in enumerate(controls):
            control_surface = self.small_font.render(control, True, self.colors['ui_text'])
            self.screen.blit(control_surface, (10, controls_y + i * 20))
    
    def _update_visual_effects(self):
        """Update visual effects like particles and audio visualization."""
        # Generate dust particles when car is sliding
        if self.player_car.tire_squeal_intensity > 0.5:
            if random.random() < 0.3:  # Occasional particle
                self._add_dust_particle(self.player_car.x, self.player_car.y)
        
        # Update audio visualization values
        self.engine_volume_visual = self.player_car.engine_sound_pitch
        self.tire_squeal_visual = self.player_car.tire_squeal_intensity
    
    def _add_dust_particle(self, x: float, y: float):
        """Add dust particle at given position."""
        if len(self.particles) > 100:  # Limit particles
            return
        
        particle = {
            'x': x + random.uniform(-10, 10),
            'y': y + random.uniform(-10, 10),
            'vel_x': random.uniform(-1, 1),
            'vel_y': random.uniform(-1, 1),
            'life': 30,
            'max_life': 30,
            'color': (100, 80, 60)  # Dust color
        }
        
        self.particles.append(particle)
    
    def _update_fps(self):
        """Update FPS counter."""
        self.frame_count += 1
        current_time = pygame.time.get_ticks()
        
        if current_time - self.last_fps_time >= 1000:  # Update every second
            self.fps_counter = self.frame_count
            self.frame_count = 0
            self.last_fps_time = current_time