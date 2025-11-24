import math
import random
from typing import Dict, List, Tuple, Optional

# ---------------------------------------------------------------------------
# Procedural track generation with:
#   - Spline-smoothed centerline
#   - Inner/outer boundaries (offset normals)
#   - Optional deterministic seed for reproducible tracks
#   - Width + complexity parameters
#   - Extra guards to avoid self-overlap at high width/complexity
# ---------------------------------------------------------------------------


def generate_track(
    width: int = 50,
    complexity: int = 10,
    seed: Optional[int] = None,
    intended_weather: str = "CLEAR"
) -> Dict:
    """
    Generate a closed racing track.

    Args:
        width: approximate width of the asphalt band (pixels).
        complexity: number of control points / corners.
        seed: if provided, a deterministic seed for reproducibility.

    Returns:
        dict with:
          - centerline: list of (x,y)
          - inner_boundary: list of (x,y)
          - outer_boundary: list of (x,y)
          - racing_line: list of (x,y)
          - checkpoints: list of dicts
          - start_pos: (x,y)
          - start_angle: float (radians)
          - width: effective width actually used for geometry
          - seed: seed used for generation
    """
    rng = random.Random(seed) if seed is not None else random

    cx, cy = 600, 400
    base_r = 260

    # 1) Rough ring of noisy control points
    n_ctrl = max(6, complexity)
    controls: List[Tuple[float, float]] = []
    for i in range(n_ctrl):
        a = 2 * math.pi * i / n_ctrl + rng.uniform(-0.18, 0.18)
        r = base_r * rng.uniform(0.80, 1.20)
        controls.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    # 2) Smooth them with Chaikin's algorithm.
    #    When complexity is high, use extra smoothing to avoid kinks
    #    that can cause boundaries to fold over.
    chaikin_iters = 2
    if complexity >= 14:
        chaikin_iters = 3
    if complexity >= 20:
        chaikin_iters = 4
    controls = _chaikin_loop(controls, iters=chaikin_iters)

    # 3) Dense Catmull-Rom centerline
    center = _catmull_rom_loop(controls, samples=8 * n_ctrl)

    # 4) Offset inner/outer boundaries with curvature-based pinch guard.
    #    For very wide and very complex tracks, shrink the effective
    #    width a bit internally to reduce self-overlap.
    effective_width = float(width)
    if complexity >= 14:
        effective_width *= 0.9
    if complexity >= 18:
        effective_width *= 0.8
    if width >= 70:
        effective_width *= 0.9

    inner, outer = _offset_boundaries(center, effective_width)

    # Sanity: ensure 'inner' is inside 'outer', otherwise swap
    if inner and outer:
        step = max(1, len(inner) // 12)
        if any(not _point_in_polygon(inner[i], outer) for i in range(0, len(inner), step)):
            inner, outer = outer, inner

    # 5) Racing line (simple curvature-aware bias between inner/outer)
    racing = _racing_line(center, inner, outer)

    # 6) Checkpoints
    checkpoints = _checkpoints(center, 8)

    start_pos = center[0]
    start_angle = math.atan2(center[1][1] - center[0][1], center[1][0] - center[0][0])

    # 7) Check valid weather
    assert intended_weather in ["CLEAR", "RAIN", "SNOW"]

    return {
        "centerline": center,
        "inner_boundary": inner,
        "outer_boundary": outer,
        "racing_line": racing,
        "checkpoints": checkpoints,
        "start_pos": start_pos,
        "start_angle": start_angle,
        "width": effective_width,  # geometry width actually used
        "seed": seed,
        "intended_weather": intended_weather
    }


# ---------------------------------------------------------------------------
# Helper geometry
# ---------------------------------------------------------------------------

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


def _chaikin_loop(pts: List[Tuple[float, float]], iters: int = 1) -> List[Tuple[float, float]]:
    """Chaikin's corner-cutting algorithm for closed loops."""
    for _ in range(iters):
        out: List[Tuple[float, float]] = []
        n = len(pts)
        for i in range(n):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            out.extend([q, r])
        pts = out
    return pts


def _catmull_rom_loop(controls: List[Tuple[float, float]], samples: int) -> List[Tuple[float, float]]:
    """Uniform Catmull-Rom spline interpolation on a closed loop."""
    n = len(controls)
    pts: List[Tuple[float, float]] = []
    seg_samples = max(6, samples // n)
    for i in range(n):
        p0 = controls[(i - 1) % n]
        p1 = controls[i]
        p2 = controls[(i + 1) % n]
        p3 = controls[(i + 2) % n]
        for k in range(seg_samples):
            t = k / seg_samples
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            pts.append((x, y))
    return pts


def _offset_boundaries(center: List[Tuple[float, float]], width: float):
    """
    Offset inner and outer boundaries from centerline using averaged normals.
    Includes a stronger curvature-based pinch guard so inner boundary does not
    collapse onto the centerline on tight corners, especially when the track
    is very wide or very wiggly.
    """
    half = width / 2.0
    inner: List[Tuple[float, float]] = []
    outer: List[Tuple[float, float]] = []
    n = len(center)
    for i in range(n):
        p_prev = center[(i - 1) % n]
        p = center[i]
        p_next = center[(i + 1) % n]

        # Tangent based on prev/next
        tx, ty = (p_next[0] - p_prev[0], p_next[1] - p_prev[1])
        L = (tx * tx + ty * ty) ** 0.5 or 1.0
        tx, ty = tx / L, ty / L

        # Left-hand normal
        nx, ny = -ty, tx

        # Curvature estimate (angle between segments)
        v1x, v1y = (p[0] - p_prev[0], p[1] - p_prev[1])
        v2x, v2y = (p_next[0] - p[0], p_next[1] - p[1])
        L1 = (v1x * v1x + v1y * v1y) ** 0.5 or 1.0
        L2 = (v2x * v2x + v2y * v2y) ** 0.5 or 1.0
        c = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (L1 * L2)))
        theta = math.acos(c)  # 0 (straight) .. pi (U-turn)

        # Curvature in [0,1]
        curv_norm = theta / math.pi

        # Wider tracks + sharper turns → stronger pinch.
        width_scale = min(1.0, width / 60.0)  # 0 when narrow, ~1 when very wide
        # Max pinch amount (up to 45% shrink) scaled by width & curvature.
        pinch_amount = min(0.45, curv_norm * 1.2 * width_scale)
        pinch = 1.0 - pinch_amount

        # Never let the corridor completely vanish
        pinch = max(0.40, pinch)

        inner.append((p[0] - nx * half * pinch, p[1] - ny * half * pinch))
        outer.append((p[0] + nx * half * pinch, p[1] + ny * half * pinch))

    return inner, outer


def _racing_line(center, inner, outer):
    """Simplified curvature-based racing line between inner and outer."""
    out = []
    n = len(center)
    for i in range(n):
        p0 = center[(i - 1) % n]
        p1 = center[i]
        p2 = center[(i + 1) % n]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        L1 = (v1[0] * v1[0] + v1[1] * v1[1]) ** 0.5 or 1.0
        L2 = (v2[0] * v2[0] + v2[1] * v2[1]) ** 0.5 or 1.0
        curv = (v1[0] * v2[1] - v1[1] * v2[0]) / (L1 * L2)
        bias = min(0.6, abs(curv) * 8.0)
        target = inner[i] if curv > 0 else outer[i]
        out.append(_lerp(p1, target, bias))
    return out


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _checkpoints(center: List[Tuple[float, float]], n_ck: int):
    cps = []
    step = len(center) // n_ck
    for i in range(n_ck):
        idx = (i * step) % len(center)
        nxt = (idx + 1) % len(center)
        cps.append(
            {
                "position": center[idx],
                "direction": (
                    center[nxt][0] - center[idx][0],
                    center[nxt][1] - center[idx][1],
                ),
                "index": i,
                "passed": False,
            }
        )
    return cps
