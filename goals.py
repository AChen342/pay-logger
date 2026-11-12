"""Local settings kept next to the app in goals.json: income goals, and
the days you usually work.

They're personal settings rather than data, so they stay out of the
Google Sheet -- and out of git (*.json is ignored).
"""
import json
import os

GOALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goals.json")
KEYS = ("weekly", "monthly", "yearly")
WORKDAYS_KEY = "workdays"


def _read():
    try:
        with open(GOALS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(data):
    with open(GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load():
    """{"weekly": float|None, "monthly": ..., "yearly": ...}."""
    raw = _read()
    out = {}
    for k in KEYS:
        try:
            v = float(raw.get(k))
            out[k] = v if v > 0 else None
        except (TypeError, ValueError):
            out[k] = None
    return out


def save(goals):
    """Write the goals, leaving the workdays alone."""
    data = _read()
    data.update({k: goals.get(k) for k in KEYS})
    _write(data)


def load_workdays():
    """The weekdays usually worked, as a sorted list of 0=Monday..6=Sunday.
    Empty when the user hasn't said -- the forecast then counts only the
    shifts actually on the calendar."""
    raw = _read().get(WORKDAYS_KEY) or []
    try:
        return sorted({int(v) for v in raw if 0 <= int(v) <= 6})
    except (TypeError, ValueError):
        return []


def save_workdays(days):
    """Write the usual workdays, leaving the goals alone."""
    data = _read()
    data[WORKDAYS_KEY] = sorted({int(v) for v in days if 0 <= int(v) <= 6})
    _write(data)
