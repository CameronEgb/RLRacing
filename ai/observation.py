import pygame
import numpy as np
import math

class VisionProcessor:
    def __init__(self, obs_size=(64, 64), camera_zoom_size=(128, 128)):
        self.obs_size = obs_size
        self.camera_zoom_size = camera_zoom_size
        
        # Pre-calculate surface sizes
        self.large_size = int(max(camera_zoom_size) * 1.5)
        self.camera_surface = pygame.Surface((self.large_size, self.large_size))
        
        # --- SCHEMATIC COLORS (High Contrast for NEW Vision Training) ---
        self.COLOR_GRASS = (255, 255, 255) 
        self.COLOR_ROAD_OUTER = (0, 0, 0)
        self.COLOR_ROAD_INNER = (255, 255, 255)
        self.COLOR_CAR = (128, 128, 128)

        # --- LEGACY COLORS (Realistic/Low Contrast for OLD Models) ---
        self.LEGACY_GRASS = (70, 105, 70)
        self.LEGACY_ROAD_OUTER = (45, 45, 45)
        self.LEGACY_ROAD_INNER = (70, 105, 70)
        self.LEGACY_CAR = (255, 0, 0)

        # --- RAYCASTING SETTINGS (For Numeric Mode) ---
        self.ray_angles = [0, 15, 30, 45, 90, -15, -30, -45, -90]
        self.ray_length = 300 

    def get_observation(self, car, track, obs_type="VISION"):
        """
        Switch between Vision types and Numeric observations.
        """
        if obs_type == "VISION":
            # High Contrast Vision
            return self._get_vision_obs(car, track, legacy=False)
        elif obs_type == "LEGACY":
            # Original Low Contrast Vision
            return self._get_vision_obs(car, track, legacy=True)
        elif obs_type == "NUMERIC":
            return self._get_numeric_obs(car, track)
        else:
            # Default to Legacy if unknown string passed
            return self._get_vision_obs(car, track, legacy=True)

    def _get_vision_obs(self, car, track, legacy=False):
        """
        Returns a (H, W, 1) or (H, W) numpy array depending on mode.
        """
        # Select Color Palette
        if legacy:
            c_grass = self.LEGACY_GRASS
            c_road_out = self.LEGACY_ROAD_OUTER
            c_road_in = self.LEGACY_ROAD_INNER
            c_car = self.LEGACY_CAR
        else:
            c_grass = self.COLOR_GRASS
            c_road_out = self.COLOR_ROAD_OUTER
            c_road_in = self.COLOR_ROAD_INNER
            c_car = self.COLOR_CAR

        # 1. Clear the canvas
        self.camera_surface.fill(c_grass)

        cx, cy = self.large_size // 2, self.large_size // 2
        car_x, car_y = car.x, car.y

        def offset(points):
            return [(p[0] - car_x + cx, p[1] - car_y + cy) for p in points]

        # 2. Draw Track
        if track:
            if "outer_boundary" in track and len(track["outer_boundary"]) > 2:
                poly_out = offset(track["outer_boundary"])
                pygame.draw.polygon(self.camera_surface, c_road_out, poly_out)
            
            if "inner_boundary" in track and len(track["inner_boundary"]) > 2:
                poly_in = offset(track["inner_boundary"])
                pygame.draw.polygon(self.camera_surface, c_road_in, poly_in)

        # 3. Draw Car
        car_poly = car.get_corners()
        car_poly_shifted = [(p[0] - car_x + cx, p[1] - car_y + cy) for p in car_poly]
        pygame.draw.polygon(self.camera_surface, c_car, car_poly_shifted)

        # 4: Rotate
        angle_deg = math.degrees(car.angle)
        rotated_surf = pygame.transform.rotate(self.camera_surface, angle_deg)
        
        # 5. Center Crop
        rot_rect = rotated_surf.get_rect()
        crop_rect = pygame.Rect(0, 0, self.obs_size[0], self.obs_size[1])
        crop_rect.center = rot_rect.center
        final_surf = rotated_surf.subsurface(crop_rect)
        
        # 6. Convert to Grayscale
        arr = pygame.surfarray.array3d(final_surf)
        arr = np.transpose(arr, (1, 0, 2))
        gray = np.dot(arr[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
        
        # 7. Dimension Handling
        if legacy:
            # Legacy models expect (64, 64) WITHOUT channel dim
            # VecFrameStack will make it (4, 64, 64)
            return gray
        else:
            # New Vision models expect (64, 64, 1) WITH channel dim
            # VecFrameStack will make it (4, 64, 64, 1)
            return np.expand_dims(gray, axis=-1)

    def _get_numeric_obs(self, car, track):
        """
        Returns a 1D numpy array of float32.
        """
        lidar_readings = []
        car_pos = np.array([car.x, car.y])
        
        walls = []
        if track:
            walls.extend(self._poly_to_segments(track.get("outer_boundary", [])))
            walls.extend(self._poly_to_segments(track.get("inner_boundary", [])))

        car_angle = car.angle
        
        for angle_offset in self.ray_angles:
            theta = car_angle + math.radians(angle_offset)
            ray_dir = np.array([math.cos(theta), math.sin(theta)])
            ray_end = car_pos + ray_dir * self.ray_length
            dist = self._cast_ray(car_pos, ray_end, walls)
            lidar_readings.append(dist)

        lidar_norm = np.array(lidar_readings, dtype=np.float32) / self.ray_length
        speed_norm = car.get_speed_kmh() / 150.0 
        steering_norm = car.steering 

        obs = np.concatenate((lidar_norm, [speed_norm, steering_norm]))
        return obs.astype(np.float32)

    def _poly_to_segments(self, poly):
        segments = []
        if not poly or len(poly) < 2:
            return segments
        for i in range(len(poly)):
            p1 = poly[i]
            p2 = poly[(i + 1) % len(poly)]
            segments.append((p1, p2))
        return segments

    def _cast_ray(self, start, end, segments):
        closest_dist = self.ray_length
        x3, y3 = start
        x4, y4 = end
        
        for p1, p2 in segments:
            x1, y1 = p1
            x2, y2 = p2
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if den == 0: continue 
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
            if 0 <= t <= 1 and 0 <= u <= 1:
                ix = x1 + t * (x2 - x1)
                iy = y1 + t * (y2 - y1)
                dist = math.hypot(ix - x3, iy - y3)
                if dist < closest_dist:
                    closest_dist = dist
        return closest_dist