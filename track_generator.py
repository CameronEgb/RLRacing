import math
import random
import pygame
from typing import List, Tuple, Dict

def generate_track(width: int = 50, complexity: int = 8) -> Dict:
    """
    Generates a procedural racing track using spline interpolation.
    
    Algorithm:
    1. Create random control points in a roughly circular pattern
    2. Use Catmull-Rom spline interpolation for smooth curves
    3. Generate track boundaries and collision geometry
    4. Calculate racing line for AI opponents
    5. Place checkpoints for lap detection
    
    Args:
        width: Track width in pixels
        complexity: Number of control points (higher = more complex track)
    
    Returns:
        Dict containing track data, boundaries, start position, etc.
    """
    
    # Generate control points in a rough circle with random variations
    control_points = []
    center_x, center_y = 600, 400  # Screen center roughly
    base_radius = 250
    
    for i in range(complexity):
        angle = (2 * math.pi * i) / complexity
        
        # Add randomness to radius and angle for interesting track shapes
        radius_variation = random.uniform(0.7, 1.4)
        angle_variation = random.uniform(-0.3, 0.3)
        
        radius = base_radius * radius_variation
        actual_angle = angle + angle_variation
        
        x = center_x + radius * math.cos(actual_angle)
        y = center_y + radius * math.sin(actual_angle)
        
        control_points.append((x, y))
    
    # Generate smooth track using Catmull-Rom splines
    track_centerline = generate_smooth_spline(control_points, 200)
    
    # Create track boundaries (inner and outer walls)
    track_inner, track_outer = generate_track_boundaries(track_centerline, width)
    
    # Calculate optimal racing line for AI
    racing_line = calculate_racing_line(track_centerline, track_inner, track_outer)
    
    # Generate checkpoints for lap detection
    checkpoints = generate_checkpoints(track_centerline, 8)
    
    # Determine start position and angle
    start_pos = track_centerline[0]
    start_angle = math.atan2(
        track_centerline[1][1] - track_centerline[0][1],
        track_centerline[1][0] - track_centerline[0][0]
    )
    
    return {
        'centerline': track_centerline,
        'inner_boundary': track_inner,
        'outer_boundary': track_outer,
        'racing_line': racing_line,
        'checkpoints': checkpoints,
        'start_pos': start_pos,
        'start_angle': start_angle,
        'width': width
    }

def generate_smooth_spline(control_points: List[Tuple[float, float]], 
                          resolution: int) -> List[Tuple[float, float]]:
    """
    Generate smooth spline using Catmull-Rom interpolation.
    This creates naturally curved racing tracks that feel realistic.
    """
    if len(control_points) < 4:
        return control_points
    
    # Close the loop by adding first few points to the end
    extended_points = control_points + control_points[:3]
    spline_points = []
    
    for i in range(len(control_points)):
        p0 = extended_points[i]
        p1 = extended_points[i + 1]
        p2 = extended_points[i + 2]
        p3 = extended_points[i + 3]
        
        # Generate points along this segment
        segment_resolution = resolution // len(control_points)
        for t_step in range(segment_resolution):
            t = t_step / segment_resolution
            point = catmull_rom_point(p0, p1, p2, p3, t)
            spline_points.append(point)
    
    return spline_points

def catmull_rom_point(p0: Tuple[float, float], p1: Tuple[float, float], 
                      p2: Tuple[float, float], p3: Tuple[float, float], 
                      t: float) -> Tuple[float, float]:
    """
    Calculate point on Catmull-Rom spline.
    This mathematical technique creates smooth curves through control points.
    """
    t2 = t * t
    t3 = t2 * t
    
    x = 0.5 * ((2 * p1[0]) +
               (-p0[0] + p2[0]) * t +
               (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
               (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
    
    y = 0.5 * ((2 * p1[1]) +
               (-p0[1] + p2[1]) * t +
               (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
               (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
    
    return (x, y)

def generate_track_boundaries(centerline: List[Tuple[float, float]], 
                             width: int) -> Tuple[List[Tuple[float, float]], 
                                                  List[Tuple[float, float]]]:
    """
    Generate inner and outer track boundaries by offsetting centerline.
    Uses perpendicular vectors to create consistent track width.
    """
    inner_boundary = []
    outer_boundary = []
    half_width = width / 2
    
    for i in range(len(centerline)):
        current = centerline[i]
        next_point = centerline[(i + 1) % len(centerline)]
        
        # Calculate direction vector
        dx = next_point[0] - current[0]
        dy = next_point[1] - current[1]
        length = math.sqrt(dx*dx + dy*dy)
        
        if length > 0:
            # Normalize direction vector
            dx /= length
            dy /= length
            
            # Perpendicular vector (rotated 90 degrees)
            perp_x = -dy
            perp_y = dx
            
            # Create inner and outer points
            inner_x = current[0] + perp_x * half_width
            inner_y = current[1] + perp_y * half_width
            outer_x = current[0] - perp_x * half_width
            outer_y = current[1] - perp_y * half_width
            
            inner_boundary.append((inner_x, inner_y))
            outer_boundary.append((outer_x, outer_y))
        else:
            inner_boundary.append(current)
            outer_boundary.append(current)
    
    return inner_boundary, outer_boundary

def calculate_racing_line(centerline: List[Tuple[float, float]], 
                         inner: List[Tuple[float, float]], 
                         outer: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Calculate optimal racing line using racing theory:
    - Late apex for tight corners
    - Early apex for chicanes
    - Maximize radius of curvature
    """
    racing_line = []
    
    for i in range(len(centerline)):
        # Analyze curvature at this point
        prev_idx = (i - 1) % len(centerline)
        next_idx = (i + 1) % len(centerline)
        
        # Calculate curvature using three points
        curvature = calculate_curvature(
            centerline[prev_idx], 
            centerline[i], 
            centerline[next_idx]
        )
        
        # Adjust line based on curvature
        if abs(curvature) > 0.01:  # Significant curve
            # For curves, move toward inside of turn
            bias = min(0.7, abs(curvature) * 50)  # Stronger bias for sharper turns
            if curvature > 0:  # Left turn
                racing_point = interpolate_point(centerline[i], inner[i], bias)
            else:  # Right turn
                racing_point = interpolate_point(centerline[i], outer[i], bias)
        else:
            # Straight sections - stay near centerline
            racing_point = centerline[i]
        
        racing_line.append(racing_point)
    
    return racing_line

def calculate_curvature(p1: Tuple[float, float], p2: Tuple[float, float], 
                       p3: Tuple[float, float]) -> float:
    """Calculate curvature at middle point using three consecutive points."""
    # Vector from p1 to p2
    v1 = (p2[0] - p1[0], p2[1] - p1[1])
    # Vector from p2 to p3  
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    
    # Cross product gives curvature direction and magnitude
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    v1_len = math.sqrt(v1[0]**2 + v1[1]**2)
    v2_len = math.sqrt(v2[0]**2 + v2[1]**2)
    
    if v1_len > 0 and v2_len > 0:
        return cross / (v1_len * v2_len)
    return 0

def interpolate_point(p1: Tuple[float, float], p2: Tuple[float, float], 
                     t: float) -> Tuple[float, float]:
    """Linear interpolation between two points."""
    return (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)

def generate_checkpoints(centerline: List[Tuple[float, float]], 
                        num_checkpoints: int) -> List[Dict]:
    """Generate evenly spaced checkpoints for lap detection."""
    checkpoints = []
    interval = len(centerline) // num_checkpoints
    
    for i in range(num_checkpoints):
        idx = (i * interval) % len(centerline)
        next_idx = (idx + 1) % len(centerline)
        
        pos = centerline[idx]
        direction = (
            centerline[next_idx][0] - pos[0],
            centerline[next_idx][1] - pos[1]
        )
        
        checkpoints.append({
            'position': pos,
            'direction': direction,
            'index': i,
            'passed': False
        })
    
    return checkpoints