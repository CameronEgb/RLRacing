import os
from config import MODELS_DIR, TRACKS_DIR

class AIOppSession:
    def __init__(self):
        self.active = False
        self.track_file = None
        self.track_name = None
        self.model_path = None
        self.obs_type = "LEGACY" # Default fallback for old models
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
        # Priority Order:
        # 1. NUMERIC (The new Fast PoC)
        # 2. VISION (The new High Contrast)
        # 3. LEGACY (Your original unoptimized Vision)
        # 4. DEFAULT (If folder has no suffix, assume it's the original/Legacy)
        
        candidates = [
            (f"{self.track_name}_NUMERIC", "NUMERIC"),
            (f"{self.track_name}_VISION", "VISION"),
            (f"{self.track_name}_LEGACY", "LEGACY"),
            (f"{self.track_name}", "LEGACY") # Fallback to Legacy for un-suffixed folders
        ]

        found = False
        for folder_name, detected_type in candidates:
            # We look for the 'best_model.zip' created by EvalCallback
            potential_path = os.path.join(MODELS_DIR, folder_name, "best_model/best_model.zip")
            
            if os.path.exists(potential_path):
                self.model_path = potential_path
                self.obs_type = detected_type
                print(f"[AI Mode] Auto-detected {detected_type} model at: {self.model_path}")
                found = True
                break
        
        if not found:
            self.model_path = None
            # If nothing found, defaults to LEGACY so random agent doesn't crash
            self.obs_type = "LEGACY" 
            print(f"[AI Mode] No trained model found for {self.track_name}. Falling back to Random AI.")

    def record_win(self, winner):
        self.winner = winner

    def is_finished(self):
        # Single race mode
        return self.winner is not None