import os
from config import MODELS_DIR, TRACKS_DIR

class AIOppSession:
    def __init__(self):
        self.active = False
        self.track_file = None
        self.track_name = None
        self.model_path = None
        self.obs_type = "VISION" # Default fallback
        self.winner = None
    
    def start(self, track_filename):
        """
        Starts the session for a specific track file.
        Autodetects the best model based on the track name and observation type.
        """
        self.active = True
        self.winner = None
        self.track_file = os.path.join(TRACKS_DIR, track_filename)
        
        # Derive track name from filename (e.g., "master_track.json" -> "master_track")
        self.track_name = os.path.splitext(track_filename)[0]
        
        # ---------------------------------------------------------
        # INTELLIGENT MODEL SEARCH
        # ---------------------------------------------------------
        # We check for models in this priority order:
        # 1. NUMERIC (Fastest, newest PoC)
        # 2. VISION (High contrast CNN)
        # 3. LEGACY (Old folder structure)
        
        candidates = [
            (f"{self.track_name}_NUMERIC", "NUMERIC"),
            (f"{self.track_name}_VISION", "VISION"),
            (f"{self.track_name}", "VISION") # Assume legacy folder is Vision
        ]

        found = False
        for folder_name, detected_type in candidates:
            # We look for the 'best_model.zip' created by EvalCallback
            # path: models/{track_name}_{TYPE}/best_model/best_model.zip
            potential_path = os.path.join(MODELS_DIR, folder_name, "best_model/best_model.zip")
            
            if os.path.exists(potential_path):
                self.model_path = potential_path
                self.obs_type = detected_type
                print(f"[AI Mode] Auto-detected {detected_type} model at: {self.model_path}")
                found = True
                break
        
        if not found:
            self.model_path = None
            self.obs_type = "VISION" # Default to numeric if random fallback
            print(f"[AI Mode] No trained model found for {self.track_name}. Falling back to Random AI.")

    def record_win(self, winner):
        self.winner = winner

    def is_finished(self):
        # Single race mode
        return self.winner is not None