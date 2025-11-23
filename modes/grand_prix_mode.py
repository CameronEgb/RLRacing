# modes/grand_prix_mode.py
from config import GP_RACES_PER_CUP

class GrandPrixSession:
    def __init__(self):
        self.active = False
        self.cup_index = 0
        self.race_index = 0
        self.player_wins = 0
        self.ai_wins = 0
        self.last_race_winner = None

    def start(self, cup_index, difficulty, weather):
        self.active = True
        self.cup_index = cup_index
        self.race_index = 0
        self.player_wins = self.ai_wins = 0
        self.difficulty = difficulty
        self.weather = weather

    def record_win(self, winner):
        self.last_race_winner = winner
        if winner == "PLAYER":
            self.player_wins += 1
        elif winner == "AI":
            self.ai_wins += 1

    def next_race(self):
        self.race_index += 1

    def is_finished(self):
        return self.race_index >= GP_RACES_PER_CUP

    def get_final_winner(self):
        if self.player_wins > self.ai_wins:
            return "PLAYER"
        if self.ai_wins > self.player_wins:
            return "AI"
        return "TIE"