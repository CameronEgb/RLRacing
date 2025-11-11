import math
import random
from typing import List, Tuple, Dict

def generate_track(width: int = 50, complexity: int = 10) -> Dict:
    """
    Smooth closed track with clear asphalt ring and infield grass.
    Keeps inner truly inside outer; avoids pinches.
    """
    cx, cy = 600, 400
    base_r = 260

    # 1) Rough ring of controls
    n_ctrl = max(6, complexity)
    controls = []
    for i in range(n_ctrl):
        a = 2 * math.pi * i / n_ctrl + random.uniform(-0.18, 0.18)
        r = base_r * random.uniform(0.80, 1.20)
        controls.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    # 2) Smooth (Chaikin)
    controls = _chaikin_loop(controls, iters=2)

    # 3) Dense Catmull-Rom centerline
    center = _catmull_rom_loop(controls, samples=8 * n_ctrl)

    # 4) Offset inner/outer with a gentle pinch-guard
    inner, outer = _offset_boundaries(center, width)

    # Sanity guard: inner must be inside outer (swap if orientation flipped)
    if inner and outer:
        step = max(1, len(inner) // 12)
        if any(not _point_in_polygon(inner[i], outer) for i in range(0, len(inner), step)):
            inner, outer = outer, inner

    # 5) Racing line (curvature-aware bias)
    racing = _racing_line(center, inner, outer)

    # 6) Checkpoints
    checkpoints = _checkpoints(center, 8)

    start_pos = center[0]
    start_angle = math.atan2(center[1][1] - center[0][1], center[1][0] - center[0][0])

    return {
        "centerline": center,
        "inner_boundary": inner,
        "outer_boundary": outer,
        "racing_line": racing,
        "checkpoints": checkpoints,
        "start_pos": start_pos,
        "start_angle": start_angle,
        "width": width,
    }

# ---------------- helpers ----------------

def _point_in_polygon(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1):
            inside = not inside
    return inside

def _chaikin_loop(pts: List[Tuple[float, float]], iters=1) -> List[Tuple[float, float]]:
    for _ in range(iters):
        out = []
        n = len(pts)
        for i in range(n):
            p0 = pts[i]; p1 = pts[(i + 1) % n]
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            out.extend([q, r])
        pts = out
    return pts

def _catmull_rom_loop(controls: List[Tuple[float, float]], samples: int) -> List[Tuple[float, float]]:
    n = len(controls)
    pts = []
    seg_samples = max(6, samples // n)
    for i in range(n):
        p0 = controls[(i - 1) % n]
        p1 = controls[i]
        p2 = controls[(i + 1) % n]
        p3 = controls[(i + 2) % n]
        for k in range(seg_samples):
            t = k / seg_samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            pts.append((x, y))
    return pts

def _offset_boundaries(center: List[Tuple[float, float]], width: int):
    """Average normal offset + gentle pinch so inner never intrudes on asphalt."""
    half = width / 2.0
    inner, outer = [], []
    n = len(center)
    for i in range(n):
        p_prev = center[(i - 1) % n]
        p = center[i]
        p_next = center[(i + 1) % n]

        # averaged tangent & unit normal (left-hand)
        tx, ty = (p_next[0] - p_prev[0], p_next[1] - p_prev[1])
        L = (tx * tx + ty * ty) ** 0.5 or 1.0
        tx, ty = tx / L, ty / L
        nx, ny = -ty, tx

        # curvature estimate
        v1x, v1y = (p[0] - p_prev[0], p[1] - p_prev[1])
        v2x, v2y = (p_next[0] - p[0], p_next[1] - p[1])
        L1 = (v1x * v1x + v1y * v1y) ** 0.5 or 1.0
        L2 = (v2x * v2x + v2y * v2y) ** 0.5 or 1.0
        c = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (L1 * L2)))
        theta = math.acos(c)

        # gentler pinch (keeps a healthy minimum width)
        pinch = 1.0 - min(0.15, (theta / math.pi) * 0.4)

        inner.append((p[0] - nx * half * pinch, p[1] - ny * half * pinch))
        outer.append((p[0] + nx * half * pinch, p[1] + ny * half * pinch))

    return inner, outer

def _racing_line(center, inner, outer):
    out = []
    n = len(center)
    for i in range(n):
        p0 = center[(i - 1) % n]; p1 = center[i]; p2 = center[(i + 1) % n]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        L1 = (v1[0] * v1[0] + v1[1] * v1[1]) ** 0.5 or 1.0
        L2 = (v2[0] * v2[0] + v2[1] * v2[1]) ** 0.5 or 1.0
        curv = (v1[0] * v2[1] - v1[1] * v2[0]) / (L1 * L2)
        bias = min(0.6, abs(curv) * 8.0)
        tgt = inner[i] if curv > 0 else outer[i]
        out.append((p1[0] + (tgt[0] - p1[0]) * bias, p1[1] + (tgt[1] - p1[1]) * bias))
    return out

def _checkpoints(center: List[Tuple[float, float]], n_ck: int):
    cps = []
    step = len(center) // n_ck
    for i in range(n_ck):
        idx = (i * step) % len(center)
        nxt = (idx + 1) % len(center)
        cps.append({
            "position": center[idx],
            "direction": (center[nxt][0] - center[idx][0], center[nxt][1] - center[idx][1]),
            "index": i,
            "passed": False
        })
    return cps
