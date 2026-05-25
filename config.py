# config.py
import json
from pathlib import Path

CONFIG_FILE = Path("config.json")


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def get(key):
    return load_config()[key]


def set(key, value):
    config = load_config()
    config[key] = value
    save_config(config)
