# utils.py
import math

def compute_grid_positions(track_data):
    start = track_data["start_pos"]
    cx, cy = start
    centerline = track_data.get("centerline") or []

    if len(centerline) < 2:
        return (cx, cy), (cx - 40, cy)

    c0, c1 = centerline[0], centerline[1]
    tx = c1[0] - c0[0]
    ty = c1[1] - c0[1]
    length = math.hypot(tx, ty) or 1.0
    tx, ty = tx / length, ty / length
    nx, ny = -ty, tx

    offset = max(8.0, track_data.get("width", 50) * 0.22)
    return (cx - nx * offset, cy - ny * offset), (cx + nx * offset, cy + ny * offset)