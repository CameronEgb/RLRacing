# reward_recorder.py
import math
from game.car import Car

class HumanRewardRecorder:
    """
    EXACT duplicate of RacingEnv.step() reward logic.
    Now safe: no distance calculation until the player car is bound.
    """
    def __init__(self, track_data):
        self.track_data = track_data
        self.total_reward = 0.0
        self.step_count = 0

        self.car = None  # Will be set on first update()
        self.next_checkpoint_idx = 1
        self.prev_distance_to_checkpoint = 0.0

    def _dist_to_checkpoint(self, idx):
        if self.car is None:
            return 0.0

        cp_list = self.track_data["checkpoints"]
        cp = cp_list[idx % len(cp_list)]

        if isinstance(cp, dict):
            if "pos" in cp:
                cx, cy = cp["pos"]
            elif "position" in cp:
                cx, cy = cp["position"]
            elif "center" in cp:
                cx, cy = cp["center"]
            else:
                cx, cy = 0, 0
        else:
            cx, cy = cp[0], cp[1] if isinstance(cp, (list, tuple)) else (cp, cp)

        return math.hypot(self.car.x - cx, self.car.y - cy)

    def _dist_to_centerline(self):
        if self.car is None:
            return 0.0
        min_dist = float('inf')
        for px, py in self.track_data["centerline"]:
            d = math.hypot(self.car.x - px, self.car.y - py)
            min_dist = min(min_dist, d)
        return min_dist

    def update(self, car: Car, dt: float = 1/30.0):
        # Bind car on first call
        if self.car is None:
            self.car = car
            # Now that we have a car, initialise the first distance
            self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)

        self.step_count += 1
        step_reward = 0.0

        # 1. Time penalty
        step_reward -= 0.05

        # 2. Progress reward
        dist_to_cp = self._dist_to_checkpoint(self.next_checkpoint_idx)
        raw_progress = self.prev_distance_to_checkpoint - dist_to_cp
        raw_progress = max(min(raw_progress, 10.0), -10.0)
        step_reward += raw_progress * 0.3
        self.prev_distance_to_checkpoint = dist_to_cp

        # 3. Checkpoint & lap bonus
        if dist_to_cp < 40:
            step_reward += 2.0
            self.next_checkpoint_idx = (self.next_checkpoint_idx + 1) % len(self.track_data["checkpoints"])
            self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)

            if self.next_checkpoint_idx == 0:
                step_reward += 10.0  # lap bonus

        # 4. Centering penalty
        track_half_width = self.track_data["width"] / 2
        dist_from_center = self._dist_to_centerline()
        norm_dist = dist_from_center / track_half_width

        if norm_dist > 1.0:
            step_reward -= 5.0
        else:
            step_reward -= (norm_dist ** 4) * 0.5

        self.total_reward += step_reward

        # Live print every second
        if self.step_count % 30 == 0:
            print(f"[HUMAN REWARD] Step {self.step_count:4d} | "
                  f"StepR {step_reward:+7.3f} | Total {self.total_reward:8.2f}")

        return self.total_reward

    def get_total(self):
        return self.total_reward

    def reset(self):
        self.total_reward = 0.0
        self.step_count = 0
        self.next_checkpoint_idx = 1
        if self.car is not None:
            self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)