from __future__ import annotations
import math
from typing import Dict, Tuple, List


# --- Surface speed caps (km/h) ---
ASPHALT_MAX_KMH = 25.0
GRASS_MAX_KMH   = 10.0
OFFRD_MAX_KMH   = 7.0

# convert to px/s using the HUD’s 1 px/s ≈ 0.36 km/h
ASPHALT_MAX_PX = ASPHALT_MAX_KMH / 0.36
GRASS_MAX_PX   = GRASS_MAX_KMH   / 0.36
OFFRD_MAX_PX   = OFFRD_MAX_KMH   / 0.36


class Car:
    """
    Top-down car with:
      • forward accel/brake + drag
      • speed-scaled steering
      • substep integration (anti-tunneling)
      • grass = driveable slowdown; hard wall only at outer boundary
      • per-surface speed caps (25 km/h asphalt, 10 km/h grass)
      • get_corners() returns world-space polygon; drawn vertical by UX offset here
    """

    def __init__(
        self,
        x: float,
        y: float,
        angle: float,
        color: tuple = (255, 0, 100),
        max_speed: float = 1800.0,   # soft cap; hard caps are surface-based above
        acceleration: float = 180.0, # slightly gentler so it feels controlled
        turning_speed: float = 2.4,
        friction: float = 0.988,     # per-60fps base
        name: str = "Car",
    ):
        self.x, self.y = float(x), float(y)
        self.angle = float(angle)

        self.color = color
        self.name = name
        self.width = 20
        self.height = 34

        self.max_speed = float(max_speed)
        self.acceleration_rate = float(acceleration)
        self.turning_speed = float(turning_speed)
        self.base_friction = float(friction)

        self.velocity_x = 0.0
        self.velocity_y = 0.0

        self.throttle = 0.0
        self.steering = 0.0
        self.handbrake = False

    # ---------------- input / lifecycle ----------------

    def set_input(self, throttle: float, steering: float, handbrake: bool = False):
        self.throttle = max(-1.0, min(1.0, float(throttle)))
        self.steering = max(-1.0, min(1.0, float(steering)))
        self.handbrake = bool(handbrake)

    def reset(self, x: float, y: float, angle: float):
        self.x, self.y, self.angle = float(x), float(y), float(angle)
        self.velocity_x = self.velocity_y = 0.0
        self.throttle = self.steering = 0.0
        self.handbrake = False

    # ---------------- geometry helpers ----------------

    @staticmethod
    def _point_in_polygon(point: Tuple[float, float], poly: List[Tuple[float, float]]) -> bool:
        x, y = point
        inside = False
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
            if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1):
                inside = not inside
        return inside

    @staticmethod
    def _closest_point_on_segment(p, a, b):
        ax, ay = a; bx, by = b; px, py = p
        abx, aby = bx - ax, by - ay
        ab2 = abx * abx + aby * aby
        if ab2 <= 1e-12:
            return a
        t = ((px - ax) * abx + (py - ay) * aby) / ab2
        t = max(0.0, min(1.0, t))
        return (ax + abx * t, ay + aby * t)

    def _nearest_on_boundaries(self, point, track_data):
        best = None; best_d2 = 1e18; which = None
        for tag in ("inner_boundary", "outer_boundary"):
            poly = track_data.get(tag) or []
            for i in range(len(poly)):
                q = self._closest_point_on_segment(point, poly[i], poly[(i + 1) % len(poly)])
                d2 = (q[0] - point[0]) ** 2 + (q[1] - point[1]) ** 2
                if d2 < best_d2:
                    best_d2 = d2; best = q; which = "inner" if tag == "inner_boundary" else "outer"
        nx = point[0] - best[0]; ny = point[1] - best[1]
        L = (nx * nx + ny * ny) ** 0.5 or 1.0
        return best, (nx / L, ny / L), which

    # ---------------- surface classification ----------------

    def _surface_type(self, track_data: Dict) -> str:
        """
        'asphalt'  : inside outer AND outside inner
        'grass'    : inside inner (infield) but still inside outer
        'offroad'  : outside outer
        """
        pos = (self.x, self.y)
        outer = track_data.get("outer_boundary") or []
        inner = track_data.get("inner_boundary") or []

        inside_outer = self._point_in_polygon(pos, outer) if outer else True
        if not inside_outer:
            return "offroad"
        inside_inner = self._point_in_polygon(pos, inner) if inner else False
        return "grass" if inside_inner else "asphalt"

    # ---------------- physics core (single substep) ----------------

    def _update_once(self, dt: float, track_data: Dict):
        # Forward (screen Y down)
        c = math.cos(self.angle); s = math.sin(self.angle)
        fx, fy = c, s

        # Longitudinal accel
        a_long = self.acceleration_rate * self.throttle
        if self.handbrake:
            a_long *= 0.35

        self.velocity_x += fx * a_long * dt
        self.velocity_y += fy * a_long * dt

        # Soft overall cap (rarely hit because surface caps below)
        sp = math.hypot(self.velocity_x, self.velocity_y)
        if sp > self.max_speed:
            k = self.max_speed / (sp + 1e-9)
            self.velocity_x *= k; self.velocity_y *= k

        # Steering
        steer_gain = self.turning_speed * (0.5 + 0.5 * min(1.0, sp / 400.0))
        self.angle += steer_gain * self.steering * dt

        # Drag (time-scaled)
        decay = self.base_friction ** (dt * 60.0)
        self.velocity_x *= decay; self.velocity_y *= decay

        # Integrate
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt

    # ---------------- hard wall (only outside outer) ----------------

    def _enforce_outer_wall(self, track_data: Dict, margin=3.0, bounce=0.05, damp=0.72):
        pos = (self.x, self.y)
        outer = track_data.get("outer_boundary") or []
        if not outer:
            return
        if self._point_in_polygon(pos, outer):
            return

        q, (nx, ny), _ = self._nearest_on_boundaries(pos, track_data)
        # Push inward
        self.x = q[0] - nx * margin
        self.y = q[1] - ny * margin

        vn = self.velocity_x * nx + self.velocity_y * ny
        self.velocity_x = (self.velocity_x - (1.0 + bounce) * vn * nx) * damp
        self.velocity_y = (self.velocity_y - (1.0 + bounce) * vn * ny) * damp

        # Tangential slide
        tx, ty = -ny, nx
        vt = self.velocity_x * tx + self.velocity_y * ty
        if abs(vt) < 70.0:
            vt = 70.0 if vt >= 0 else -70.0
        self.velocity_x = vt * tx
        self.velocity_y = vt * ty

    # ---------------- public update with substeps & surface caps ----------------

    def update(self, dt: float, track_data: Dict):
        # Fixed substeps
        max_sub_dt = 1.0 / 240.0
        steps = max(1, int(dt / max_sub_dt) + 1)
        sub_dt = dt / steps

        # Time-scaled slowdowns (gentle on grass; harsher offroad)
        GRASS_DECAY = 0.985
        OFFRD_DECAY = 0.94

        for _ in range(steps):
            self._update_once(sub_dt, track_data)

            # Surface effects + hard surface speed caps
            surf = self._surface_type(track_data)
            sp = math.hypot(self.velocity_x, self.velocity_y)

            if surf == "asphalt":
                vmax = ASPHALT_MAX_PX
            elif surf == "grass":
                vmax = GRASS_MAX_PX
                factor = GRASS_DECAY ** (sub_dt * 60.0)
                self.velocity_x *= factor; self.velocity_y *= factor
            else:  # offroad
                vmax = OFFRD_MAX_PX
                factor = OFFRD_DECAY ** (sub_dt * 60.0)
                self.velocity_x *= factor; self.velocity_y *= factor

            # enforce hard cap for the surface
            if sp > vmax:
                k = vmax / (sp + 1e-9)
                self.velocity_x *= k
                self.velocity_y *= k

            # Only outer boundary is a hard wall
            self._enforce_outer_wall(track_data)

    # ---------------- drawing geometry (vertical look) ----------------

    def get_corners(self) -> List[Tuple[float, float]]:
        VISUAL_YAW = -math.pi / 2  # make car look vertical
        a = self.angle + VISUAL_YAW
        c, s = math.cos(a), math.sin(a)
        hw, hh = self.width / 2, self.height / 2
        rect = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        pts = []
        for dx, dy in rect:
            xw = self.x + c * dx - s * dy
            yw = self.y + s * dx + c * dy
            pts.append((xw, yw))
        return pts

    # HUD helpers
    def get_speed_kmh(self) -> float:
        return math.hypot(self.velocity_x, self.velocity_y) * 0.36

    def get_rpm(self) -> int:
        sp = min(self.max_speed, math.hypot(self.velocity_x, self.velocity_y))
        return int(1000 + (sp / max(1.0, self.max_speed)) * 6000)
