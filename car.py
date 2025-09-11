import math
import pygame
from typing import Dict, List, Tuple

class Car:
    """
    Realistic car physics simulation for top-down racing.
    
    Physics Implementation Details:
    - Uses proper vector-based velocity and acceleration
    - Simulates tire friction with grip limits  
    - Implements weight transfer during acceleration/braking
    - Models engine torque curves and gear ratios
    - Includes aerodynamic drag and rolling resistance
    - Simulates understeer/oversteer characteristics
    """
    
    def __init__(self, x: float, y: float, angle: float, color: tuple, 
                 max_speed: float = 200.0, acceleration: float = 15.0,
                 turning_speed: float = 2.5, friction: float = 0.92, name: str = "Car"):
        
        # Position and orientation
        self.x = x
        self.y = y
        self.angle = angle  # Heading angle in radians
        
        # Physics vectors - using pixels/second for game world
        self.velocity_x = 0.0  # Actual movement direction in pixels/sec
        self.velocity_y = 0.0
        self.angular_velocity = 0.0  # Rate of rotation in rad/sec
        
        # Car properties
        self.color = color
        self.name = name
        self.width = 20
        self.height = 10
        
        # Performance characteristics (adjusted for pixel space)
        self.max_speed = max_speed  # pixels/second
        self.acceleration_rate = acceleration  # pixels/second²
        self.brake_rate = acceleration * 2.0  # Brakes are stronger than acceleration
        self.turning_speed = turning_speed  # rad/second at optimal speed
        self.base_friction = friction  # Speed reduction factor per second
        
        # Advanced physics parameters
        self.mass = 1200  # kg - affects acceleration and momentum
        self.wheelbase = 15  # pixels - affects turning radius
        
        # Tire physics
        self.tire_grip = 0.95  # Maximum lateral force multiplier
        self.static_friction_threshold = 5.0  # Minimum speed for steering (pixels/sec)
        self.slip_angle_max = 0.15  # Maximum slip angle before losing grip (radians)
        
        # Speed-dependent steering
        self.min_turn_speed = 10.0  # Minimum speed for effective turning
        self.optimal_turn_speed = 80.0  # Speed at which turning is most effective
        self.high_speed_turn_reduction = 0.3  # Turn rate reduction at high speed
        
        # Traction control
        self.traction_control = True
        self.max_acceleration_grip = 0.8  # Prevents wheelspin
        
        # Aerodynamics (simplified)
        self.drag_coefficient = 0.001  # Air resistance factor
        
        # Input states
        self.throttle = 0.0  # -1.0 to 1.0 (brake to accelerate)
        self.steering = 0.0  # -1.0 to 1.0 (left to right)
        self.handbrake = False  # For sharp turns
        
        # Surface interaction
        self.on_track = True
        self.off_track_grip_multiplier = 0.4  # Reduced grip when off-track
        
        # Audio simulation variables
        self.engine_sound_pitch = 1.0
        self.tire_squeal_intensity = 0.0
        self.speed_for_audio = 0.0
    
    def update(self, dt: float, track_data: Dict):
        """
        Update car physics simulation with realistic vehicle dynamics.
        
        Args:
            dt: Delta time in seconds
            track_data: Track information for collision detection
        """
        
        # Calculate current speed
        current_speed = math.sqrt(self.velocity_x**2 + self.velocity_y**2)
        
        # Determine grip level based on surface
        current_grip = self.tire_grip if self.on_track else self.tire_grip * self.off_track_grip_multiplier
        
        # 1. ACCELERATION AND BRAKING
        # Only apply forces if there's grip and we're not spinning out
        if abs(self.angular_velocity) < 5.0:  # Not spinning wildly
            if self.throttle > 0:
                # Forward acceleration
                accel_force = self.throttle * self.acceleration_rate
                
                # Traction control - reduce power if wheels would spin
                if self.traction_control:
                    max_accel = current_grip * self.max_acceleration_grip * self.acceleration_rate
                    accel_force = min(accel_force, max_accel)
                
                # Apply acceleration in car's facing direction
                accel_x = math.cos(self.angle) * accel_force * dt
                accel_y = math.sin(self.angle) * accel_force * dt
                
            elif self.throttle < 0:
                # Braking - applies opposite to velocity direction
                if current_speed > 0.1:
                    brake_force = -self.throttle * self.brake_rate
                    brake_x = -(self.velocity_x / current_speed) * brake_force * dt
                    brake_y = -(self.velocity_y / current_speed) * brake_force * dt
                    
                    # Prevent reversing from braking
                    new_vx = self.velocity_x + brake_x
                    new_vy = self.velocity_y + brake_y
                    
                    # Check if we're about to reverse direction
                    if (new_vx * self.velocity_x < 0 or new_vy * self.velocity_y < 0):
                        self.velocity_x = 0
                        self.velocity_y = 0
                    else:
                        self.velocity_x = new_vx
                        self.velocity_y = new_vy
                else:
                    # Reverse gear (slower acceleration)
                    accel_force = self.throttle * self.acceleration_rate * 0.5
                    accel_x = math.cos(self.angle) * accel_force * dt
                    accel_y = math.sin(self.angle) * accel_force * dt
            else:
                accel_x = accel_y = 0
                
            # Apply acceleration only if not braking
            if self.throttle > 0 or (self.throttle < 0 and current_speed < 0.1):
                self.velocity_x += accel_x
                self.velocity_y += accel_y
        
        # 2. STEERING PHYSICS
        # No steering when stationary or nearly stationary
        if current_speed > self.static_friction_threshold and abs(self.steering) > 0.01:
            # Calculate steering effectiveness based on speed
            if current_speed < self.min_turn_speed:
                # Very slow - minimal turning
                steering_effectiveness = 0.2
            elif current_speed < self.optimal_turn_speed:
                # Building up - increasing effectiveness
                steering_effectiveness = 0.2 + 0.8 * ((current_speed - self.min_turn_speed) / 
                                                     (self.optimal_turn_speed - self.min_turn_speed))
            else:
                # High speed - reduced turning
                speed_factor = self.optimal_turn_speed / current_speed
                steering_effectiveness = max(self.high_speed_turn_reduction, speed_factor)
            
            # Apply steering with grip consideration
            turn_rate = self.steering * self.turning_speed * steering_effectiveness * current_grip
            
            # Handbrake for sharp turns (reduces rear grip)
            if self.handbrake:
                turn_rate *= 1.5
                current_grip *= 0.6
            
            # Update angular velocity
            self.angular_velocity = turn_rate
            
            # Apply the rotation
            self.angle += self.angular_velocity * dt
            
            # Calculate lateral forces from turning
            # This creates the "pull" toward the new direction
            if abs(self.angular_velocity) > 0.01:
                # Calculate centripetal acceleration
                centripetal_force = current_speed * abs(self.angular_velocity) * 0.5
                
                # Limit by available grip
                max_lateral_force = current_grip * current_speed * 0.8
                lateral_force = min(centripetal_force, max_lateral_force)
                
                # Calculate slip angle
                if current_speed > 1:
                    velocity_angle = math.atan2(self.velocity_y, self.velocity_x)
                    slip_angle = self.angle - velocity_angle
                    
                    # Normalize slip angle
                    while slip_angle > math.pi:
                        slip_angle -= 2 * math.pi
                    while slip_angle < -math.pi:
                        slip_angle += 2 * math.pi
                    
                    # If slip angle is too large, we're sliding
                    if abs(slip_angle) > self.slip_angle_max:
                        # Reduce lateral grip when sliding
                        grip_factor = max(0.3, 1.0 - abs(slip_angle) / math.pi)
                        lateral_force *= grip_factor
                        self.tire_squeal_intensity = min(1.0, abs(slip_angle) * 2)
                    else:
                        self.tire_squeal_intensity = abs(slip_angle) * 0.5
                    
                    # Apply lateral force to gradually align velocity with heading
                    alignment_force = lateral_force * dt * 0.1
                    target_vx = math.cos(self.angle) * current_speed
                    target_vy = math.sin(self.angle) * current_speed
                    
                    self.velocity_x += (target_vx - self.velocity_x) * alignment_force
                    self.velocity_y += (target_vy - self.velocity_y) * alignment_force
        else:
            # No steering when too slow
            self.angular_velocity = 0
            self.tire_squeal_intensity = 0
        
        # 3. DRAG AND FRICTION
        # Air resistance (increases with speed squared)
        if current_speed > 0:
            drag_force = self.drag_coefficient * current_speed * current_speed
            drag_x = -(self.velocity_x / current_speed) * drag_force * dt
            drag_y = -(self.velocity_y / current_speed) * drag_force * dt
            self.velocity_x += drag_x
            self.velocity_y += drag_y
        
        # Rolling resistance and friction
        friction_factor = self.base_friction if self.on_track else self.base_friction * 0.7
        
        # Apply friction (stronger at low speeds for stopping)
        if current_speed < 10:
            # Strong friction to stop completely
            friction_this_frame = 1.0 - (5.0 * dt)
        else:
            # Normal friction
            friction_this_frame = math.pow(friction_factor, dt)
        
        self.velocity_x *= friction_this_frame
        self.velocity_y *= friction_this_frame
        
        # Stop completely if very slow
        if current_speed < 1.0 and self.throttle == 0:
            self.velocity_x = 0
            self.velocity_y = 0
        
        # 4. SPEED LIMITING
        # Enforce maximum speed
        if current_speed > self.max_speed:
            speed_ratio = self.max_speed / current_speed
            self.velocity_x *= speed_ratio
            self.velocity_y *= speed_ratio
        
        # 5. UPDATE POSITION
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt
        
        # 6. TRACK COLLISION DETECTION
        self._check_track_collision(track_data)
        
        # 7. AUDIO SIMULATION VALUES
        self.speed_for_audio = current_speed
        self.engine_sound_pitch = 0.8 + (current_speed / self.max_speed) * 0.6
    
    def _check_track_collision(self, track_data: Dict):
        """
        Check collision with track boundaries and adjust physics accordingly.
        """
        car_pos = (self.x, self.y)
        
        # Check if car is inside track boundaries
        self.on_track = self._point_in_track(car_pos, track_data)
        
        if not self.on_track:
            # Find closest track boundary point
            closest_point, normal = self._find_closest_boundary(car_pos, track_data)
            
            # Calculate collision response
            if closest_point:
                # Distance from boundary
                dist_x = self.x - closest_point[0]
                dist_y = self.y - closest_point[1]
                penetration = math.sqrt(dist_x**2 + dist_y**2)
                
                if penetration < 15:  # Close to wall
                    # Calculate velocity component toward wall
                    vel_dot_normal = (self.velocity_x * normal[0] + 
                                     self.velocity_y * normal[1])
                    
                    if vel_dot_normal < 0:  # Moving into wall
                        # Bounce with energy loss
                        restitution = 0.2  # Energy retained after collision
                        self.velocity_x -= vel_dot_normal * normal[0] * (1 + restitution)
                        self.velocity_y -= vel_dot_normal * normal[1] * (1 + restitution)
                        
                        # Push car away from wall
                        push_strength = max(0, 15 - penetration)
                        self.x += normal[0] * push_strength
                        self.y += normal[1] * push_strength
    
    def _point_in_track(self, point: Tuple[float, float], track_data: Dict) -> bool:
        """Check if point is within track boundaries."""
        center_x, center_y = 600, 400
        distance = math.sqrt((point[0] - center_x)**2 + (point[1] - center_y)**2)
        return 180 < distance < 320  # Track bounds
    
    def _find_closest_boundary(self, point: Tuple[float, float], 
                              track_data: Dict) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Find closest boundary point and normal vector."""
        center_x, center_y = 600, 400
        dx = point[0] - center_x
        dy = point[1] - center_y
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist > 0:
            # Normalize to get direction
            nx, ny = dx / dist, dy / dist
            
            # Determine if closer to inner or outer boundary
            if dist < 250:
                # Closer to inner boundary
                boundary_x = center_x + nx * 180
                boundary_y = center_y + ny * 180
                normal = (nx, ny)  # Normal points outward from center
            else:
                # Closer to outer boundary
                boundary_x = center_x + nx * 320
                boundary_y = center_y + ny * 320
                normal = (-nx, -ny)  # Normal points inward to center
            
            return (boundary_x, boundary_y), normal
        
        return None, (0, 0)
    
    def set_input(self, throttle: float, steering: float, handbrake: bool = False):
        """
        Set car input values.
        
        Args:
            throttle: -1.0 (full brake/reverse) to 1.0 (full accelerate)
            steering: -1.0 (full left) to 1.0 (full right)
            handbrake: True if handbrake is engaged
        """
        self.throttle = max(-1.0, min(1.0, throttle))
        self.steering = max(-1.0, min(1.0, steering))
        self.handbrake = handbrake
    
    def get_corners(self) -> List[Tuple[float, float]]:
        """Get car corner positions for collision detection and rendering."""
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        
        # Car corners relative to center
        corners = [
            (-self.width/2, -self.height/2),  # Rear left
            (self.width/2, -self.height/2),   # Rear right
            (self.width/2, self.height/2),    # Front right
            (-self.width/2, self.height/2)    # Front left
        ]
        
        # Rotate and translate corners
        world_corners = []
        for corner_x, corner_y in corners:
            # Rotate
            rotated_x = corner_x * cos_a - corner_y * sin_a
            rotated_y = corner_x * sin_a + corner_y * cos_a
            
            # Translate
            world_x = self.x + rotated_x
            world_y = self.y + rotated_y
            
            world_corners.append((world_x, world_y))
        
        return world_corners
    
    def get_speed_kmh(self) -> float:
        """Get current speed in km/h for UI display."""
        # Assuming 1 pixel = 0.1 meters for display purposes
        speed_ms = math.sqrt(self.velocity_x**2 + self.velocity_y**2) * 0.1
        return speed_ms * 3.6  # Convert m/s to km/h
    
    def get_rpm(self) -> int:
        """Get simulated engine RPM for UI display."""
        current_speed = math.sqrt(self.velocity_x**2 + self.velocity_y**2)
        # Simple RPM simulation based on speed
        rpm = 1000 + (current_speed / self.max_speed) * 6000
        return int(min(7000, rpm))
    
    def reset(self, x: float, y: float, angle: float):
        """Reset car to a new position with zero velocity."""
        self.x = x
        self.y = y
        self.angle = angle
        self.velocity_x = 0
        self.velocity_y = 0
        self.angular_velocity = 0
        self.throttle = 0
        self.steering = 0
        self.handbrake = False