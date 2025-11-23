import json
import os

def save_track(track_data: dict, filename: str = "master_track.json"):
    """
    Saves the track data to a JSON file.
    """
    try:
        with open(filename, "w") as f:
            json.dump(track_data, f, indent=2)
        print(f"Track saved to {filename}")
    except Exception as e:
        print(f"Error saving track: {e}")

def load_track(filename: str = "master_track.json") -> dict:
    """
    Loads track data from a JSON file.
    """
    if not os.path.exists(filename):
        return None
    
    try:
        with open(filename, "r") as f:
            track_data = json.load(f)
        
        # JSON converts tuples to lists. We need to ensure consistency.
        # While Pygame usually handles lists fine, let's just use the data as loaded.
        print(f"Track loaded from {filename}")
        return track_data
    except Exception as e:
        print(f"Error loading track: {e}")
        return None