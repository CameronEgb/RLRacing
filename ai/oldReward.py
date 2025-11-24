self.car.set_input(throttle, steering)
            self.car.update(1.0 / 30.0, self.track)
            
            # --- REWARD LOGIC ---
            dontStayStill = -0.05
            total_reward -= dontStayStill

            dist_to_cp = self._dist_to_checkpoint(self.next_checkpoint_idx)
            progress = self.prev_distance_to_checkpoint - dist_to_cp
            total_reward += progress * 0.1
            self.prev_distance_to_checkpoint = dist_to_cp

            if dist_to_cp < 40:
                total_reward += 2.0
                self.next_checkpoint_idx = (self.next_checkpoint_idx + 1) % len(self.track["checkpoints"])
                self.prev_distance_to_checkpoint = self._dist_to_checkpoint(self.next_checkpoint_idx)
                if self.next_checkpoint_idx == 0:
                    self.lap_count += 1
                    total_reward += 5.0

            speed = self.car.get_speed_kmh()
            total_reward += speed * 0.005
            
            track_width = self.track["width"]
            dist_from_center = self._dist_to_centerline()
            on_grass_thresh = (track_width / 2) * 0.8
            hit_wall_thresh = (track_width / 2)
            
            if dist_from_center > hit_wall_thresh:
                total_reward -= 1.0
                #terminated = True
            elif dist_from_center > on_grass_thresh:
                total_reward -= 0.2