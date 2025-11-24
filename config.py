# config.py
import pygame
import os

SCREEN_WIDTH, SCREEN_HEIGHT = 1200, 800
FPS = 60

CHECKPOINT_RADIUS = 24.0
COLLISION_RADIUS_PLAYER = COLLISION_RADIUS_AI = 15.0
START_MOVE_RADIUS = 40.0

ARCADE_WINS_TARGET = 3
GP_RACES_PER_CUP = 3

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKS_DIR = os.path.join(BASE_DIR, "tracks")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# Ensure they exist
os.makedirs(TRACKS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

CUP_NAMES = ["Forest Cup", "Canyon Cup", "City Cup"]

GP_CUPS = {
    0: [  # Forest Cup
        {"name": "Forest Ring",    "seed": 1111, "width": 52, "complexity": 9},
        {"name": "Forest Chicane", "seed": 1112, "width": 48, "complexity": 12},
        {"name": "Forest Sprint",  "seed": 1113, "width": 54, "complexity": 10},
    ],
    1: [  # Canyon Cup
        {"name": "Canyon Loop",    "seed": 2221, "width": 58, "complexity": 11},
        {"name": "Canyon Switch",  "seed": 2222, "width": 60, "complexity": 13},
        {"name": "Canyon Run",     "seed": 2223, "width": 56, "complexity": 12},
    ],
    2: [  # City Cup
        {"name": "City Circuit",   "seed": 3331, "width": 46, "complexity": 10},
        {"name": "City Hairpins",  "seed": 3332, "width": 44, "complexity": 13},
        {"name": "City Sprint",    "seed": 3333, "width": 48, "complexity": 11},
    ],
}

DIFFICULTIES = ["EASY", "NORMAL", "HARD"]
WEATHERS = ["CLEAR", "RAIN", "SNOW"]

pygame.font.init()
FONT_TITLE = pygame.font.SysFont("arial", 32, bold=True)
FONT_BTN = pygame.font.SysFont("arial", 22)
FONT_SMALL = pygame.font.SysFont("arial", 18)
FONT_HUD = pygame.font.SysFont("arial", 20, bold=True)
FONT_COUNTDOWN = pygame.font.SysFont("arial", 80, bold=True)