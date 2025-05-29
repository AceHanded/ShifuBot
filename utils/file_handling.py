import json

def load_roles() -> dict:
    with open("./data/roles.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_settings() -> dict:
    with open("./data/settings.json", "r", encoding="utf-8") as f:
        return json.load(f)
