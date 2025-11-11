import pygame as pg
from typing import Dict


class GameUX:
    def __init__(self, screen, track_data: Dict, player_car, ai_car):
        self.screen = screen
        self.track = track_data
        self.player = player_car
        self.ai = ai_car
        self.font = pg.font.SysFont("arial", 18)
        self.hud_font = pg.font.SysFont("arial", 22)
        self.bg_color = (110, 130, 150)
        self.grass_color = (70, 105, 70)
        self.asphalt_color = (45, 45, 45)

    def _draw_track(self):
        sc = self.screen
        inner = self.track.get("inner_boundary") or []
        outer = self.track.get("outer_boundary") or []
        center = self.track.get("centerline") or []

        # Background water/sky
        sc.fill(self.bg_color)

        # Grass infield + surroundings
        if outer:
            pg.draw.polygon(sc, self.grass_color, outer, 0)
        if inner:
            # carve the infield back to grass (keeps green center visible)
            pg.draw.polygon(sc, self.grass_color, inner, 0)

        # Asphalt ring: draw outer as dark, then cut inner with GRASS color
        if outer:
            pg.draw.polygon(sc, self.asphalt_color, outer, 0)
        if inner:
            pg.draw.polygon(sc, self.grass_color, inner, 0)

        # Optional lane marks: dashed dots along center
        if len(center) > 1:
            for i in range(0, len(center), 12):
                pg.draw.circle(sc, (80, 80, 80), (int(center[i][0]), int(center[i][1])), 2)

        # Checkpoints
        for cp in self.track.get("checkpoints", []):
            x, y = cp["position"]
            pg.draw.circle(sc, (230, 200, 80), (int(x), int(y)), 10, 2)

    def _draw_car(self, car, label: str):
        pts = car.get_corners()  # already rotated world-space
        pg.draw.polygon(self.screen, car.color, pts, 0)
        pg.draw.lines(self.screen, (240, 240, 240), True, pts, 2)
        # label
        cx = sum(p[0] for p in pts) / 4.0
        cy = sum(p[1] for p in pts) / 4.0 - 18
        t = self.font.render(label, True, (240, 240, 240))
        self.screen.blit(t, (cx - t.get_width() / 2, cy - t.get_height() / 2))

    def _draw_hud(self):
        speed = int(self.player.get_speed_kmh())
        rpm = self.player.get_rpm()
        lines = [f"Speed: {speed} km/h", f"RPM: {rpm}", "Engine: ▓▓▓▓▓", "Tires: ░░░░"]
        hud = pg.Surface((260, 100), pg.SRCALPHA)
        hud.fill((0, 0, 0, 120))
        for i, line in enumerate(lines):
            t = self.hud_font.render(line, True, (235, 235, 235))
            hud.blit(t, (10, 8 + i * 22))
        self.screen.blit(hud, (20, 20))

        # FPS (best effort)
        t = self.font.render("FPS: 0", True, (200, 200, 200))
        self.screen.blit(t, (self.screen.get_width() - t.get_width() - 14, 10))

        # Help
        help_lines = ["WASD / Arrow Keys: Drive", "ESC: Quit"]
        for i, line in enumerate(help_lines):
            tt = self.font.render(line, True, (200, 200, 200))
            self.screen.blit(tt, (14, self.screen.get_height() - 36 + i * 16))

    def render(self):
        self._draw_track()
        self._draw_car(self.ai, "AI Opponent")
        self._draw_car(self.player, "Player")
        self._draw_hud()
