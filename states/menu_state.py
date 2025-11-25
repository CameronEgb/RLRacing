# states/menu_state.py
import pygame
import os  # <-- critical for os.listdir and os.path
from ui.button import Button
from config import *
from game.track_storer import load_track


# ──────────────────────────────────────────────────────────────
# CUSTOM DISPLAY NAMES – edit these exactly how you want them shown!
# If a track isn't listed here, it will auto-generate a pretty name.
# ──────────────────────────────────────────────────────────────
DISPLAY_NAMES = {
    "Disc-NR-Long.json":                "1 - First Try: Discrete CNN",
    "Cont-NR-Long.json":                "2 - Second Try: Continuous CNN",
    "Cont-Lidar-R2.json":               "3 - Third Try: Continuous Lidar",
    "CLEAR-W60-C8.json":                "4 - Easy Track",
    "Final-W70-C16.json":               "5 - Medium Track",
    "RAIN-W70-C16.json":                "7 - Rainy Medium Track",
    "Final-W80-C24.json":               "6 - Hard - Reverse! Reverse!",
    "CLEAR-W80-C24.json":               "9 - ",
    "CLEAR-W70-C24.json":               "8 - Wall Rider",
    # Add new tracks here anytime – old ones stay safe!
}

# Fallback: makes "Some_Weird-File_Name.json" → "Some Weird File Name"
def pretty_filename(fname):
    name = os.path.splitext(fname)[0]
    name = name.replace("-", " ").replace("_", " ")
    return " ".join(word.capitalize() for word in name.split())


def create_button(rect, text, action=None):
    return Button(rect, text, FONT_BTN, action)


def handle_menu(game, dt):
    screen = game.screen
    mouse = pygame.mouse.get_pos()
    cx = SCREEN_WIDTH // 2

    if game.game_ux:
        game.game_ux.render()
    else:
        screen.fill((20, 40, 60))

    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    buttons = []

    # --- ROOT MENU ---
    if game.menu_substate == "root":
        title = FONT_TITLE.render("RLRacing – Main Menu", True, (240, 240, 240))
        screen.blit(title, title.get_rect(center=(cx, 200)))

        sub = FONT_SMALL.render("Choose a mode:", True, (200, 200, 200))
        screen.blit(sub, sub.get_rect(center=(cx, 250)))

        def go_arcade():
            game.menu_substate = "arcade"
            game.pending["mode"] = "ARCADE"
        
        def go_gp():
            game.menu_substate = "grand_prix"
            game.pending["mode"] = "GRAND_PRIX"
            
        def go_ai_opp():
            game.menu_substate = "ai_opp_select"
            game.pending["mode"] = "AI_OPP"

        buttons.append(create_button((cx-150, 300, 300, 50), "Arcade Mode", go_arcade))
        buttons.append(create_button((cx-150, 370, 300, 50), "Grand Prix", go_gp))
        buttons.append(create_button((cx-150, 440, 300, 50), "AI Battle (RL)", go_ai_opp))
        buttons.append(create_button((cx-150, 550, 300, 50), "Quit", lambda: setattr(game, 'running', False)))

    # --- AI TRACK SELECTION (AUTO-SORTED BY DISPLAY NUMBER) ---
    elif game.menu_substate == "ai_opp_select":
        title = FONT_TITLE.render("Select Track for AI Battle", True, (240, 240, 240))
        screen.blit(title, title.get_rect(center=(cx, 100)))
        
        try:
            track_files = [f for f in os.listdir(TRACKS_DIR) if f.endswith(".json")]
        except FileNotFoundError:
            track_files = []

        if not track_files:
            msg = FONT_SMALL.render("No tracks found in /tracks/", True, (255, 100, 100))
            screen.blit(msg, msg.get_rect(center=(cx, 300)))
        else:
            # Build a list of (display_text, filename) and sort by the number in the text
            track_items = []
            for filename in track_files:
                display_text = DISPLAY_NAMES.get(filename, pretty_filename(filename))
                track_items.append((display_text, filename))

            # Sort by the leading number (e.g. "1 - ", "2 - ", "10 - " etc.)
            def sort_key(item):
                text = item[0]
                # Find the first sequence of digits at the start (after optional spaces)
                import re
                match = re.search(r'^\s*(\d+)', text)
                return int(match.group(1)) if match else 9999  # unknown → goes to the end

            track_items.sort(key=sort_key)

            # Now create the buttons in perfect order
            start_y = 180
            spacing = 68
            for i, (display_text, filename) in enumerate(track_items):
                def make_selector(fname=filename):
                    return lambda: start_ai_race(game, fname)
                
                buttons.append(create_button(
                    (cx-280, start_y + i*spacing, 560, 58),
                    display_text,
                    make_selector()
                ))

        buttons.append(create_button((cx-100, 720, 200, 50), "Back", lambda: setattr(game, 'menu_substate', 'root')))

    # --- ARCADE MODE ---
    elif game.menu_substate == "arcade":
        title = FONT_TITLE.render("Arcade Mode", True, (240, 240, 240))
        screen.blit(title, title.get_rect(center=(cx, 100)))

        summary = FONT_SMALL.render(
            f"Difficulty: {game.pending['difficulty']}   Weather: {game.pending['weather']}   "
            f"Width: {game.pending['track_width']}   Complexity: {game.pending['complexity']}",
            True, (230, 230, 230)
        )
        screen.blit(summary, summary.get_rect(center=(cx, 150)))

        def start_race():
            game.settings.update(game.pending)
            if not game.arcade.active:
                game.arcade.start()
            game.start_race(game.settings)
            game.countdown_timer = 3.0
            game.state = "arcade_countdown"

        def cycle_diff():
            i = DIFFICULTIES.index(game.pending["difficulty"])
            game.pending["difficulty"] = DIFFICULTIES[(i+1)%3]
        def cycle_weather():
            i = WEATHERS.index(game.pending["weather"])
            game.pending["weather"] = WEATHERS[(i+1)%3]
        def open_track():
            game.menu_substate = "arcade_track"
        def apply():
            game.settings.update(game.pending)
            game.start_race(game.settings)
        def back():
            game.menu_substate = "root"

        actions = [
            ("Start Arcade Race", start_race),
            (f"Difficulty: {game.pending['difficulty']}", cycle_diff),
            (f"Weather: {game.pending['weather']}", cycle_weather),
            ("Track Options...", open_track),
            ("Apply & Preview Track", apply),
            ("Back to Mode Select", back),
        ]
        for i, (txt, act) in enumerate(actions):
            buttons.append(create_button((cx-170, 200 + i*52, 340, 44), txt, act))

    # --- ARCADE TRACK SETTINGS ---
    elif game.menu_substate == "arcade_track":
        panel = pygame.Surface((720, 400), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 200))
        screen.blit(panel, panel.get_rect(center=(cx, SCREEN_HEIGHT//2)))

        title = FONT_TITLE.render("Track Settings", True, (240, 240, 240))
        screen.blit(title, title.get_rect(center=(cx, 180)))

        def w_minus(): game.pending["track_width"] = max(30, game.pending["track_width"]-2)
        def w_plus():  game.pending["track_width"] = min(80, game.pending["track_width"]+2)
        def c_minus(): game.pending["complexity"] = max(6, game.pending["complexity"]-1)
        def c_plus():  game.pending["complexity"] = min(24, game.pending["complexity"]+1)
        def apply():
            game.settings.update(game.pending)
            game.start_race(game.settings)
        def back():
            game.menu_substate = "arcade"

        buttons = [
            create_button((cx-200, 260, 180, 44), f"Width - ({game.pending['track_width']})", w_minus),
            create_button((cx+20, 260, 180, 44), f"Width + ({game.pending['track_width']})", w_plus),
            create_button((cx-200, 320, 180, 44), f"Complexity - ({game.pending['complexity']})", c_minus),
            create_button((cx+20, 320, 180, 44), f"Complexity + ({game.pending['complexity']})", c_plus),
            create_button((cx-200, 400, 180, 44), "Apply & Preview", apply),
            create_button((cx+20, 400, 180, 44), "Back", back),
        ]

    # --- GRAND PRIX ---
    elif game.menu_substate == "grand_prix":
        title = FONT_TITLE.render("Grand Prix", True, (240, 240, 240))
        screen.blit(title, title.get_rect(center=(cx, 100)))

        def select_cup(i):
            game.pending["gp_cup_index"] = i
        def cycle_diff():
            i = DIFFICULTIES.index(game.pending["difficulty"])
            game.pending["difficulty"] = DIFFICULTIES[(i+1)%3]
        def cycle_weather():
            i = WEATHERS.index(game.pending["weather"])
            game.pending["weather"] = WEATHERS[(i+1)%3]
        def start_gp():
            game.settings.update(game.pending)
            game.grand_prix.start(game.pending["gp_cup_index"], game.pending["difficulty"], game.pending["weather"])
            preset = GP_CUPS[game.grand_prix.cup_index][0]
            settings = {**game.settings, **preset, "mode": "GRAND_PRIX"}
            game.start_race(settings)
            game.countdown_timer = 3.0
            game.state = "arcade_countdown"
        def back():
            game.menu_substate = "root"

        for i, name in enumerate(CUP_NAMES):
            color = (100, 100, 60) if game.pending["gp_cup_index"] == i else (40, 40, 40)
            pygame.draw.rect(screen, color, (cx-150, 180+i*60, 300, 50), border_radius=8)
            pygame.draw.rect(screen, (220,220,220), (cx-150, 180+i*60, 300, 50), width=2, border_radius=8)
            txt = FONT_BTN.render(name, True, (240,240,240))
            screen.blit(txt, txt.get_rect(center=(cx, 205+i*60)))
            if pygame.mouse.get_pressed()[0] and pygame.time.get_ticks() % 200 < 100:
                if (cx-150 < mouse[0] < cx+150) and (180+i*60 < mouse[1] < 230+i*60):
                    select_cup(i)

        y = 400
        buttons += [
            create_button((cx-150, y, 300, 44), f"Difficulty: {game.pending['difficulty']}", cycle_diff),
            create_button((cx-150, y+54, 300, 44), f"Weather: {game.pending['weather']}", cycle_weather),
            create_button((cx-150, y+108, 300, 44), "Start Grand Prix", start_gp),
            create_button((cx-150, y+162, 300, 44), "Back", back),
        ]

    # Draw all buttons
    for btn in buttons:
        btn.draw(screen, mouse)

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if game.menu_substate == "root":
                return False
            game.menu_substate = "root"
        for btn in buttons:
            btn.handle_event(event)

    pygame.display.flip()
    return True


def start_ai_race(game, filename):
    """Start an AI vs Player race on the selected track."""
    game.pending["mode"] = "AI_OPP"
    game.pending["track_filename"] = filename
    print("Selected track:", filename)
    track_data = load_track(os.path.join(TRACKS_DIR, filename))
    weather = track_data.get("intended_weather", "CLEAR")
    if weather != "CLEAR":
        game.pending["weather"] = weather
    game.start_race()