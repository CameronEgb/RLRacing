from __future__ import annotations
import math
import random
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Car class: kinematic top-down racing model with:
#   - Surface-aware speed limits (asphalt, grass, offroad)
#   - Realistic behavior: speed-based steering, lateral slip, grip
#   - Difficulty + weather modifiers (CLEAR / RAIN / SNOW)
#   - Outer-boundary wall projection, grass slowdown (but still driveable)
# ---------------------------------------------------------------------------

class Car:
    def __init__(
        self,
        x: float,
        y: float,
        angle: float,
        color: Tuple[int, int, int],
        name: str = "Car",
        difficulty: str = "NORMAL",
        weather: str = "CLEAR",
    ):
        # Pose
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)  # radians, 0 = right, CCW positive

        # Visuals / geometry (slightly smaller so cars can pass each other)
        self.color = color
        self.name = name
        self.width = 16   # shrunk width
        self.height = 28  # shrunk height

        # Raw kinematic state
        self.vx = 0.0  # world-space velocity (px/s)
        self.vy = 0.0

        # Inputs (from human or AI)
        self.throttle = 0.0  # -1..1 (reverse/brake .. accelerate)
        self.steering = 0.0  # -1..1 (left .. right)
        self.handbrake = False

        # Gameplay meta
        self.difficulty = difficulty.upper()
        self.weather = weather.upper()

        # Tuning parameters (filled by _refresh_tuning)
        self.engine_force = 900.0      # longitudinal accel coefficient
        self.long_drag = 0.985         # forward drag per 60fps
        self.base_steer_speed = 2.4    # base turning speed
        self.surface_speed_caps_kmh: Dict[str, float] = {}
        self.surface_grip: Dict[str, float] = {}

        self._refresh_tuning()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_input(self, throttle: float, steering: float, handbrake: bool = False) -> None:
        """Set control inputs for this frame (from keyboard or AI)."""
        self.throttle = max(-1.0, min(1.0, float(throttle)))
        self.steering = max(-1.0, min(1.0, float(steering)))
        self.handbrake = bool(handbrake)

    def set_difficulty(self, difficulty: str) -> None:
        self.difficulty = difficulty.upper()
        self._refresh_tuning()

    def set_weather(self, weather: str) -> None:
        self.weather = weather.upper()
        self._refresh_tuning()

    def reset(self, x: float, y: float, angle: float) -> None:
        """Reset pose and velocities (used for restarting races)."""
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)
        self.vx = 0.0
        self.vy = 0.0
        self.throttle = 0.0
        self.steering = 0.0
        self.handbrake = False

    # ------------------------------------------------------------------
    # Tuning / configuration
    # ------------------------------------------------------------------

    def _refresh_tuning(self) -> None:
        """
        Configure physics parameters based on difficulty + weather.
        Difficulty controls how "tame" the car feels.
        Weather primarily affects grip, drag, and speed caps.
        """
        diff = self.difficulty
        w = self.weather

        # --- Base engine & drag per difficulty (CLEAR baseline) ---
        if diff == "EASY":
            self.engine_force = 820.0
            self.long_drag = 0.988
            self.base_steer_speed = 3.0
        elif diff == "HARD":
            self.engine_force = 650.0
            self.long_drag = 0.980
            self.base_steer_speed = 2.1
        else:  # NORMAL
            self.engine_force = 750.0
            self.long_drag = 0.984
            self.base_steer_speed = 2.6

        # --- Surface speed caps (km/h) for CLEAR baseline ---
        # (scaled ~1.5x from previous: 25 -> 37.5, 10 -> 15)
        asphalt_cap = 37.5
        grass_cap   = 15.0
        offroad_cap = 7.0  # still slow offroad

        # Difficulty adjustment on CLEAR asphalt cap
        if diff == "EASY":
            asphalt_cap *= 1.1
        elif diff == "HARD":
            asphalt_cap *= 0.9

        # --- Weather adjustments to caps + engine/drag ---
        if w == "RAIN":
            # Noticeably slower and heavier than CLEAR
            self.engine_force *= 0.85
            self.long_drag = max(0.0, self.long_drag - 0.003)

            asphalt_cap *= 0.70
            grass_cap   *= 0.65
            # offroad_cap: already very low, keep as-is

        elif w == "SNOW":
            # Strongly slower and heavier than CLEAR
            self.engine_force *= 0.70
            self.long_drag = max(0.0, self.long_drag - 0.005)

            asphalt_cap *= 0.55
            grass_cap   *= 0.50
            offroad_cap *= 0.80

        # Store final caps
        self.surface_speed_caps_kmh = {
            "asphalt": asphalt_cap,
            "grass":   grass_cap,
            "offroad": offroad_cap,
        }

        # --- Lateral grip per surface & weather ---
        # Smaller value => stronger damping => more "grip"
        # Larger value (closer to 1.0) => more sideways slip.

        if w == "RAIN":
            # Clearly more slide than CLEAR
            asphalt_grip = 0.96
            grass_grip   = 0.97
            offroad_grip = 0.985
        elif w == "SNOW":
            # Very slidey / icy
            asphalt_grip = 0.985
            grass_grip   = 0.99
            offroad_grip = 0.995
        else:  # CLEAR
            asphalt_grip = 0.70
            grass_grip   = 0.90
            offroad_grip = 0.95

        # Difficulty tweaks to asphalt grip (how easy it is to keep control)
        if diff == "EASY":
            asphalt_grip *= 0.9   # stronger damping => more stable
        elif diff == "HARD":
            asphalt_grip *= 1.05  # slightly less damping => more slide

        self.surface_grip = {
            "asphalt": asphalt_grip,
            "grass":   grass_grip,
            "offroad": offroad_grip,
        }

    # ------------------------------------------------------------------
    # Surface + boundary helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _point_in_polygon(point: Tuple[float, float], poly: List[Tuple[float, float]]) -> bool:
        """Standard ray-casting point-in-polygon test."""
        x, y = point
        inside = False
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1):
                inside = not inside
        return inside

    def _surface_type(self, track_data: Dict) -> str:
        """
        Determine which surface the car is currently on.
          'asphalt'  - inside outer boundary and outside inner
          'grass'    - inside inner boundary
          'offroad'  - outside outer boundary
        """
        outer = track_data.get("outer_boundary") or []
        inner = track_data.get("inner_boundary") or []
        pos = (self.x, self.y)

        inside_outer = self._point_in_polygon(pos, outer) if outer else True
        if not inside_outer:
            return "offroad"
        inside_inner = self._point_in_polygon(pos, inner) if inner else False
        return "grass" if inside_inner else "asphalt"

    @staticmethod
    def _closest_point_on_segment(p, a, b):
        """Closest point on segment AB to point P."""
        ax, ay = a
        bx, by = b
        px, py = p
        abx = bx - ax
        aby = by - ay
        ab2 = abx * abx + aby * aby
        if ab2 <= 1e-12:
            return a
        t = ((px - ax) * abx + (py - ay) * aby) / ab2
        t = max(0.0, min(1.0, t))
        return (ax + abx * t, ay + aby * t)

    def _nearest_on_outer(self, point, track_data):
        """Find nearest point and normal on the OUTER boundary only."""
        outer = track_data.get("outer_boundary") or []
        best = None
        best_d2 = 1e18
        for i in range(len(outer)):
            q = self._closest_point_on_segment(point, outer[i], outer[(i + 1) % len(outer)])
            d2 = (q[0] - point[0]) ** 2 + (q[1] - point[1]) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = q
        if best is None:
            return point, (0.0, -1.0)
        # Outward normal from boundary to car
        nx = point[0] - best[0]
        ny = point[1] - best[1]
        L = math.hypot(nx, ny) or 1.0
        return best, (nx / L, ny / L)

    # ------------------------------------------------------------------
    # Physics integration
    # ------------------------------------------------------------------

    def _apply_outer_wall(self, track_data: Dict) -> None:
        """If car is outside outer boundary, project it back in and slide."""
        outer = track_data.get("outer_boundary") or []
        if not outer:
            return
        pos = (self.x, self.y)
        if self._point_in_polygon(pos, outer):
            return  # still inside playable area

        q, (nx, ny) = self._nearest_on_outer(pos, track_data)
        # Move car slightly inside
        margin = 3.0
        self.x = q[0] - nx * margin
        self.y = q[1] - ny * margin

        # Reflect velocity along normal (soft bounce) + preserve tangential slide
        vn = self.vx * nx + self.vy * ny
        tang_x, tang_y = -ny, nx

        vt = self.vx * tang_x + self.vy * tang_y
        # Dampen normal component, keep tangential to allow sliding along wall
        bounce = 0.1
        damp = 0.7
        self.vx = (vt * tang_x) - (1.0 + bounce) * vn * nx
        self.vy = (vt * tang_y) - (1.0 + bounce) * vn * ny
        self.vx *= damp
        self.vy *= damp

    def update(self, dt: float, track_data: Dict) -> None:
        """
        Integrate physics over timestep dt (seconds) with fixed substeps
        to avoid tunneling on tight corners or high speeds.
        """
        max_sub_dt = 1.0 / 240.0
        steps = max(1, int(dt / max_sub_dt) + 1)
        sub_dt = dt / steps

        for _ in range(steps):
            self._update_once(sub_dt, track_data)

    def _update_once(self, dt: float, track_data: Dict) -> None:
        """Single physics substep."""
        # 1) Determine surface + caps for this step
        surf = self._surface_type(track_data)
        vmax_kmh = self.surface_speed_caps_kmh.get(surf, 20.0)
        vmax = vmax_kmh / 0.36  # convert km/h to px/s

        # 2) Transform velocity into car-local frame (forward, lateral)
        c = math.cos(self.angle)
        s = math.sin(self.angle)
        # Forward axis = (c, s), right axis = (-s, c)
        v_fwd = self.vx * c + self.vy * s
        v_side = -self.vx * s + self.vy * c

        # 3) Longitudinal dynamics with realistic forward/reverse behavior
        engine = self.engine_force
        if self.handbrake:
            engine *= 0.3

        accel_forward = engine           # normal forward accel
        accel_reverse = engine * 0.6     # slower reverse
        brake_accel   = engine * 1.2     # strong braking

        # Desired throttle direction (small deadzone)
        desired = self.throttle
        if abs(desired) < 0.05:
            desired = 0.0

        # Current direction of travel along car forward axis
        if v_fwd > 1.0:
            current_dir = 1      # moving forward
        elif v_fwd < -1.0:
            current_dir = -1     # moving backward
        else:
            current_dir = 0      # nearly stopped

        if current_dir == 0:
            # From (almost) standstill: accelerate in requested direction
            if desired > 0:
                v_fwd += accel_forward * desired * dt
            elif desired < 0:
                v_fwd += accel_reverse * desired * dt
        elif current_dir == 1:
            if desired > 0:
                # normal forward acceleration
                v_fwd += accel_forward * desired * dt
            elif desired < 0:
                # braking until nearly stopped, then reverse
                if v_fwd > 0.5:
                    v_fwd -= brake_accel * abs(desired) * dt
                    if v_fwd < 0.0:
                        v_fwd = 0.0
                else:
                    # now basically stopped; start reversing
                    v_fwd += accel_reverse * desired * dt
        elif current_dir == -1:
            if desired < 0:
                # normal reversing
                v_fwd += accel_reverse * desired * dt
            elif desired > 0:
                # braking while reversing, then move forward
                if v_fwd < -0.5:
                    v_fwd += brake_accel * abs(desired) * dt  # v_fwd is negative
                    if v_fwd > 0.0:
                        v_fwd = 0.0
                else:
                    # now basically stopped; start moving forward
                    v_fwd += accel_forward * desired * dt

        # 4) Drag along forward axis
        long_decay = self.long_drag ** (dt * 60.0)
        v_fwd *= long_decay

        # 5) Lateral grip / sliding based on surface + weather
        grip = self.surface_grip.get(surf, 0.9)
        v_side *= grip ** (dt * 60.0)

        # Extra tiny lateral "wobble" in SNOW at speed (feels icy, but more obvious now)
        if self.weather == "SNOW":
            speed = abs(v_fwd)
            if speed > 40.0:
                wobble = (random.random() - 0.5) * 1.0 * (speed / 180.0)
                v_side += wobble

        # 6) Speed cap enforcement per surface
        new_speed = math.hypot(v_fwd, v_side)
        if new_speed > vmax:
            scale = vmax / (new_speed + 1e-9)
            v_fwd *= scale
            v_side *= scale

        # 7) Steering: speed-based steering with diminishing turn at high speed
        speed_for_steer = abs(v_fwd)
        steer_scale = 1.0 / (1.0 + (speed_for_steer / 350.0))
        steer_rate = self.base_steer_speed * steer_scale
        if surf == "grass":
            steer_rate *= 0.7  # harder to steer on grass

        # Weather steering nerfs (more obvious now)
        if self.weather == "RAIN":
            steer_rate *= 0.6
        elif self.weather == "SNOW":
            steer_rate *= 0.4

        self.angle += steer_rate * self.steering * dt

        # 8) Convert velocity back to world coordinates
        self.vx = v_fwd * c - v_side * s
        self.vy = v_fwd * s + v_side * c

        # 9) Integrate position
        self.x += self.vx * dt
        self.y += self.vy * dt

        # 10) Outer wall handling
        self._apply_outer_wall(track_data)

    # ------------------------------------------------------------------
    # Geometry for drawing & HUD helpers
    # ------------------------------------------------------------------

    def get_corners(self) -> List[Tuple[float, float]]:
        """
        World-space corners of the car polygon, with a visual yaw offset
        so the car appears vertical on screen (nose pointing up).
        """
        visual_yaw = -math.pi / 2  # rotate 90° CCW for drawing
        a = self.angle + visual_yaw
        c = math.cos(a)
        s = math.sin(a)
        hw = self.width / 2
        hh = self.height / 2
        rect = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        pts = []
        for dx, dy in rect:
            xw = self.x + c * dx - s * dy
            yw = self.y + s * dx + c * dy
            pts.append((xw, yw))
        return pts

    def get_speed_kmh(self) -> float:
        """Current scalar speed in km/h (for HUD only)."""
        return math.hypot(self.vx, self.vy) * 0.36

    def get_rpm(self) -> int:
        """Fake RPM for HUD visualization (just based on speed)."""
        sp = math.hypot(self.vx, self.vy)
        return int(1000 + min(sp, 2000) / 2000.0 * 6000)
