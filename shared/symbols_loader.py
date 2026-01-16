import json
import os
from pathlib import Path

def load_symbols():
    # Get the directory of this script
    current_dir = Path(__file__).parent
    json_path = current_dir / "symbols.json"
    
    if not json_path.exists():
        # Fallback for Docker environment where it might be in /app/shared/
        json_path = Path("/app/shared/symbols.json")
        
    try:
        with open(json_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading symbols.json: {e}")
        return ["BTCUSDT"] # Fallback

symbols = load_symbols()
