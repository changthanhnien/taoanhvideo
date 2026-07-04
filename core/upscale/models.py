import json
from pathlib import Path

def load_models():
    models_path = Path(__file__).parent / "models.json"
    if models_path.exists():
        with open(models_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
