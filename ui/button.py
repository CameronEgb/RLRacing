# ui/button.py
import pygame

class Button:
    def __init__(self, rect, label, font, action=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.action = action

    def draw(self, surface, mouse_pos):
        hovered = self.rect.collidepoint(mouse_pos)
        base = (40, 40, 40) if not hovered else (70, 70, 70)
        border = (220, 220, 220)
        text_color = (240, 240, 240)

        pygame.draw.rect(surface, base, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=8)

        txt = self.font.render(self.label, True, text_color)
        txt_rect = txt.get_rect(center=self.rect.center)
        surface.blit(txt, txt_rect)

    def handle_event(self, event):
        if self.action and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.action()