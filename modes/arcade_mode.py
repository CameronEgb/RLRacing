# modes/arcade_mode.py
from config import ARCADE_WINS_TARGET

class ArcadeSession:
    def __init__(self):
        self.active = False
        self.player_wins = 0
        self.ai_wins = 0
        self.last_race_winner = None

    def start(self):
        self.active = True
        self.player_wins = self.ai_wins = 0

    def record_win(self, winner):
        self.last_race_winner = winner
        if winner == "Player 1":
            self.player_wins += 1
        elif winner == "Player 2":
            self.ai_wins += 1

    def is_finished(self):
        return self.player_wins >= ARCADE_WINS_TARGET or self.ai_wins >= ARCADE_WINS_TARGET

    def get_final_winner(self):
        if self.player_wins > self.ai_wins:
            return "PLAYER"
        if self.ai_wins > self.player_wins:
            return "AI"
        return "TIE"