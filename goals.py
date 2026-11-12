"""Income goals (weekly / monthly / yearly take-home tip targets), kept in
goals.json next to the app. Local only -- they're a personal setting, not
data, so they don't go in the Google Sheet. (*.json is git-ignored.)
"""
import json
import os

GOALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goals.json")
KEYS = ("weekly", "monthly", "yearly")


def load():
    """{"weekly": float|None, "monthly": ..., "yearly": ...}."""
    try:
        with open(GOALS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    out = {}
    for k in KEYS:
        try:
            v = float(raw.get(k))
            out[k] = v if v > 0 else None
        except (TypeError, ValueError):
            out[k] = None
    return out


def save(goals):
    with open(GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump({k: goals.get(k) for k in KEYS}, f, indent=2)
