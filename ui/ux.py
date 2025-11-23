import pygame as pg
from typing import Dict, Tuple
import random


class GameUX:
    """
    Handles all rendering:
      - Background + track
      - Cars
      - HUD: speed, mode, difficulty, weather, track name
      - Weather overlays (rain/snow)
    """

    def __init__(
        self,
        screen: pg.Surface,
        track_data: Dict,
        player_car,
        ai_car,
        meta: Dict,
    ):
        self.screen = screen
        self.track = track_data
        self.player = player_car
        self.ai = ai_car

        # Meta-info: used for HUD
        self.mode = meta.get("mode", "Arcade")
        self.difficulty = meta.get("difficulty", "NORMAL")
        self.weather = meta.get("weather", "CLEAR")
        self.track_name = meta.get("track_name", "Random Track")
        self.seed = meta.get("seed", None)

        # Fonts
        self.font = pg.font.SysFont("arial", 18)
        self.hud_font = pg.font.SysFont("arial", 22)
        self.title_font = pg.font.SysFont("arial", 26, bold=True)

        # Colors
        self.bg_color = (110, 130, 150)
        self.grass_color = (70, 105, 70)
        self.asphalt_color = (45, 45, 45)

        # Weather particles
        self._snowflakes = []
        self._raindrops = []
        self._init_snow()
        self._init_rain()

    # ------------------------------------------------------------------
    # Weather particle setup
    # ------------------------------------------------------------------

    def _init_snow(self):
        """Pre-generate a small set of snowflakes; used when weather=SNOW."""
        w, h = self.screen.get_size()
        self._snowflakes = []
        for _ in range(120):
            x = random.randint(0, w)
            y = random.randint(0, h)
            speed = random.uniform(30.0, 70.0)
            drift = random.uniform(-20.0, 20.0)
            self._snowflakes.append([x, y, speed, drift])

    def _init_rain(self):
        """Pre-generate raindrops; used when weather=RAIN."""
        w, h = self.screen.get_size()
        self._raindrops = []
        for _ in range(140):
            x = random.randint(0, w)
            y = random.randint(-h, h)
            speed = random.uniform(260.0, 360.0)  # px/s downward
            self._raindrops.append([x, y, speed])

    # ------------------------------------------------------------------
    # Track drawing
    # ------------------------------------------------------------------

    def _draw_track(self):
        sc = self.screen
        inner = self.track.get("inner_boundary") or []
        outer = self.track.get("outer_boundary") or []
        center = self.track.get("centerline") or []

        # Background (water/sky)
        sc.fill(self.bg_color)

        # Grass area
        if outer:
            pg.draw.polygon(sc, self.grass_color, outer, 0)
        if inner:
            pg.draw.polygon(sc, self.bg_color, inner, 0)  # infield back to bg
            pg.draw.polygon(sc, self.grass_color, inner, 0)

        # Asphalt band
        if outer:
            pg.draw.polygon(sc, self.asphalt_color, outer, 0)
        if inner:
            pg.draw.polygon(sc, self.grass_color, inner, 0)

        # Dashed centerline
        if len(center) > 1:
            for i in range(0, len(center), 12):
                pg.draw.circle(
                    sc, (80, 80, 80), (int(center[i][0]), int(center[i][1])), 2
                )

        # Checkpoints
        for cp in self.track.get("checkpoints", []):
            x, y = cp["position"]
            center_pos = (int(x), int(y))

            # Yellow if not yet reached by player, green once player hits it
            if cp.get("player_reached", False):
                fill_color = (120, 220, 120)   # green
            else:
                fill_color = (230, 200, 80)    # yellow

            pg.draw.circle(sc, fill_color, center_pos, 8, 0)
            pg.draw.circle(sc, (0, 0, 0), center_pos, 8, 2)

    # ------------------------------------------------------------------
    # Car drawing
    # ------------------------------------------------------------------

    def _draw_car(self, car, label: str):
        pts = car.get_corners()
        pg.draw.polygon(self.screen, car.color, pts, 0)
        pg.draw.lines(self.screen, (240, 240, 240), True, pts, 2)

        cx = sum(p[0] for p in pts) / 4.0
        cy = sum(p[1] for p in pts) / 4.0 - 18
        text = self.font.render(label, True, (240, 240, 240))
        self.screen.blit(
            text,
            (cx - text.get_width() / 2, cy - text.get_height() / 2),
        )

    # ------------------------------------------------------------------
    # HUD + weather overlays
    # ------------------------------------------------------------------

    def _draw_hud(self):
        # Speed + RPM HUD
        speed = int(self.player.get_speed_kmh())
        rpm = self.player.get_rpm()
        lines = [
            f"Speed: {speed} km/h",
            f"RPM: {rpm}",
        ]
        hud = pg.Surface((220, 70), pg.SRCALPHA)
        hud.fill((0, 0, 0, 140))
        for i, line in enumerate(lines):
            t = self.hud_font.render(line, True, (235, 235, 235))
            hud.blit(t, (10, 8 + i * 26))
        self.screen.blit(hud, (20, 20))

        # Mode / difficulty / weather info (top center)
        meta_lines = [
            f"Mode: {self.mode}  |  Difficulty: {self.difficulty}",
            f"Weather: {self.weather}  |  Track: {self.track_name}",
        ]
        for i, line in enumerate(meta_lines):
            t = self.font.render(line, True, (240, 240, 240))
            rect = t.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    20 + i * 20,
                )
            )
            self.screen.blit(t, rect)

        # Controls hint (bottom-left)
        help_lines = [
            "In Race:",
            "  WASD / Arrows: Drive",
            "  ESC: Back to Menu",
            "  R: Reset",
        ]
        y0 = self.screen.get_height() - 20 - len(help_lines) * 16
        for i, line in enumerate(help_lines):
            t = self.font.render(line, True, (200, 200, 200))
            self.screen.blit(t, (16, y0 + i * 16))

    def _draw_weather_overlay(self):
        """Visual feedback for weather (RAIN/SNOW)."""
        wmode = self.weather.upper()
        if wmode == "CLEAR":
            return

        width, height = self.screen.get_size()

        if wmode == "RAIN":
            # Blue-ish tint + animated raindrops
            overlay = pg.Surface((width, height), pg.SRCALPHA)
            overlay.fill((25, 30, 60, 110))

            for drop in self._raindrops:
                x, y, speed = drop
                # Move downward (with slight diagonal slant)
                y += speed / 60.0
                x += 20.0 / 60.0  # small rightward drift

                # Respawn above the top when leaving screen
                if y > height + 20:
                    y = random.randint(-80, -10)
                    x = random.randint(-40, width + 40)
                    speed = random.uniform(260.0, 360.0)

                drop[0], drop[1], drop[2] = x, y, speed

                start = (int(x), int(y))
                end = (int(x + 3), int(y + 12))
                pg.draw.line(
                    overlay,
                    (190, 190, 255, 190),
                    start,
                    end,
                    2,
                )

            self.screen.blit(overlay, (0, 0))

        elif wmode == "SNOW":
            # Cool, light tint
            overlay = pg.Surface((width, height), pg.SRCALPHA)
            overlay.fill((210, 225, 255, 60))
            self.screen.blit(overlay, (0, 0))

            # Animate simple falling snow using cached particles
            for flake in self._snowflakes:
                x, y, speed, drift = flake
                y += speed / 60.0
                x += drift / 60.0

                if y > height:
                    y = -10
                    x = random.randint(0, width)
                    speed = random.uniform(30.0, 70.0)
                    drift = random.uniform(-20.0, 20.0)

                flake[0], flake[1], flake[2], flake[3] = x, y, speed, drift
                pg.draw.circle(self.screen, (245, 245, 255), (int(x), int(y)), 2)

    # ------------------------------------------------------------------
    # Public render
    # ------------------------------------------------------------------

    def render(self):
        self._draw_track()
        self._draw_car(self.ai, "AI Opponent")
        self._draw_car(self.player, "Player")
        self._draw_hud()
        self._draw_weather_overlay()
