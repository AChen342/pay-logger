"""The numbers behind the Dashboard and Insights screens: period totals,
the month-end forecast, goal progress, and earnings breakdowns.

Pure pandas -- no Tk, no Google -- so it can be read and tested on its own.
Everything takes the Daily DataFrame exactly as the Logger holds it
(`logger.df`) and works in take-home ("net") tips: Card + Cash - Tip Out.
"""
import math
from datetime import timedelta

import numpy as np
import pandas as pd

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday")

# How much history the forecast learns "what's a shift worth" from. Recent
# shifts say more about this month than ones from a year ago.
FORECAST_LOOKBACK_DAYS = 120
# A weekday needs this many shifts in the lookback before its own average
# is trusted over the overall one.
MIN_WEEKDAY_SAMPLES = 3


def _num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _text(s):
    return s.fillna("").astype(str).str.strip().replace({"nan": ""})


def shifts(df):
    """Daily sheet -> one clean row per shift: Date, Hours, Card, Cash,
    TipOut, Net, Type, Section, Notes, Weekday. Oldest first."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Hours", "Card", "Cash", "TipOut",
                                     "Net", "Type", "Section", "Notes", "Weekday"])
    get = lambda c: df[c] if c in df.columns else pd.Series(index=df.index, dtype=object)
    d = pd.DataFrame({
        "Date": pd.to_datetime(get("Date"), format="%m/%d/%Y", errors="coerce"),
        "Hours": _num(get("Hours")),
        "Card": _num(get("Card")),
        "Cash": _num(get("Cash")),
        "TipOut": _num(get("Tip Out")),
        "Type": _text(get("Shift Type")),
        "Section": _text(get("Section")),
        "Notes": _text(get("Notes")),
    })
    # Dates typed straight into the sheet may not be in %m/%d/%Y.
    bad = d["Date"].isna()
    if bad.any():
        d.loc[bad, "Date"] = pd.to_datetime(get("Date")[bad], errors="coerce")
    d = d.dropna(subset=["Date"])
    d["Date"] = d["Date"].dt.normalize()
    d["Net"] = d["Card"] + d["Cash"] - d["TipOut"]
    d["Weekday"] = d["Date"].dt.dayofweek
    return d.sort_values("Date").reset_index(drop=True)


def between(d, start=None, end=None):
    """Rows of a shifts() frame with start <= Date <= end (either open)."""
    if start is not None:
        d = d[d["Date"] >= pd.Timestamp(start)]
    if end is not None:
        d = d[d["Date"] <= pd.Timestamp(end)]
    return d


def totals(d):
    """Headline numbers for a shifts() frame (or slice of one)."""
    net, hours, n = float(d["Net"].sum()), float(d["Hours"].sum()), len(d)
    return {
        "net": net,
        "hours": hours,
        "shifts": n,
        "per_hour": net / hours if hours > 0 else 0.0,
        "per_shift": net / n if n else 0.0,
        "tip_out": float(d["TipOut"].sum()),
        "card": float(d["Card"].sum()),
        "cash": float(d["Cash"].sum()),
    }


# --- Periods --------------------------------------------------------------

def week_bounds(today):
    """Monday..Sunday containing `today` (matches the Weekly tab)."""
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def month_bounds(today):
    start = today.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


def year_bounds(today):
    return today.replace(month=1, day=1), today.replace(month=12, day=31)


PERIODS = {"weekly": week_bounds, "monthly": month_bounds, "yearly": year_bounds}


def period_totals(d, today):
    """{"weekly"/"monthly"/"yearly": totals()} for the period containing
    `today`, so far."""
    return {name: totals(between(d, *bounds(today)))
            for name, bounds in PERIODS.items()}


# --- Forecast -------------------------------------------------------------

def _shift_values(d, today):
    """(per-weekday average, overall average, 25th pct, 75th pct) of take-
    home per shift, learned from the last FORECAST_LOOKBACK_DAYS (or all
    history if that window is empty). None if there's no history at all."""
    recent = between(d, today - timedelta(days=FORECAST_LOOKBACK_DAYS), today)
    recent = recent[recent["Hours"] > 0]
    if recent.empty:
        recent = d[d["Hours"] > 0]
    if recent.empty:
        return None
    overall = float(recent["Net"].mean())
    by_day = {}
    for wd, grp in recent.groupby("Weekday"):
        if len(grp) >= MIN_WEEKDAY_SAMPLES:
            by_day[int(wd)] = float(grp["Net"].mean())
    p25, p75 = (float(v) for v in np.percentile(recent["Net"], [25, 75]))
    return by_day, overall, p25, p75


def _pace_shift_dates(d, today, end):
    """When the calendar isn't available: guess the remaining shifts in
    (today, end] from how many days a week you've worked lately, spread over
    your most-worked weekdays."""
    recent = between(d, today - timedelta(days=56), today)
    per_week = len(recent) / 8 if len(recent) else 0
    days_left = (end - today).days
    n = int(round(per_week * days_left / 7))
    if n <= 0:
        return []
    favs = list(recent["Weekday"].value_counts().index) or list(range(7))
    out, day = [], today + timedelta(days=1)
    while day <= end and len(out) < n:
        if day.weekday() in favs[:max(1, round(per_week))]:
            out.append(day)
        day += timedelta(days=1)
    return out


def forecast(d, today, upcoming=None, start=None, end=None):
    """Project where the period [start, end] (default: this month) will end
    up in take-home tips.

    `upcoming` is the list of future shift dates from the calendar (dates
    after today, plus today if today's shift hasn't been logged yet). If
    it's None the calendar wasn't checked, and the remaining shifts are
    guessed from your recent pace instead.

    Each remaining shift is valued at your recent average for that weekday
    (or your overall recent average, for weekdays with few samples). The
    low/high range scales that by your typical slow (25th percentile) and
    good (75th percentile) shift.

    Returns None if there's no history to learn from.
    """
    if start is None or end is None:
        start, end = month_bounds(today)
    so_far = totals(between(d, start, min(end, today)))
    vals = _shift_values(d, today)
    if vals is None:
        return None
    by_day, overall, p25, p75 = vals

    logged = set(d["Date"].dt.date)
    if upcoming is not None:
        remaining = sorted({u for u in upcoming
                            if (u > today or (u == today and u not in logged))
                            and start <= u <= end})
        source = "calendar"
    else:
        remaining = _pace_shift_dates(d, today, end)
        source = "pace"

    expected = sum(by_day.get(u.weekday(), overall) for u in remaining)
    scale_lo = p25 / overall if overall > 0 else 1.0
    scale_hi = p75 / overall if overall > 0 else 1.0
    return {
        "so_far": so_far["net"],
        "projected": so_far["net"] + expected,
        "low": so_far["net"] + expected * scale_lo,
        "high": so_far["net"] + expected * scale_hi,
        "remaining": remaining,
        "per_shift": overall,
        "source": source,
        "start": start,
        "end": end,
    }


def goal_progress(goal, so_far, projected=None, per_shift=None):
    """Progress toward one goal amount. If a projection and a per-shift
    average are given, also how many extra shifts would close the gap."""
    if not goal or goal <= 0:
        return None
    out = {"goal": goal, "so_far": so_far,
           "pct": max(0.0, min(1.0, so_far / goal)),
           "left": max(0.0, goal - so_far),
           "projected": projected, "extra_shifts": 0}
    if projected is not None and per_shift and projected < goal:
        out["extra_shifts"] = math.ceil((goal - projected) / per_shift)
    return out


# --- Insights -------------------------------------------------------------

def breakdown(d, by):
    """Average take-home per shift / per hour grouped by "Weekday", "Type"
    or "Section". Blank groups (shifts logged before details existed) are
    left out. Sorted best average shift first."""
    cols = ["Group", "Shifts", "Avg shift", "Per hour", "Total", "Hours"]
    if d.empty:
        return pd.DataFrame(columns=cols)
    d = d[d["Hours"] > 0]
    if by != "Weekday":
        d = d[d[by] != ""]
    if d.empty:
        return pd.DataFrame(columns=cols)
    g = d.groupby(by).agg(Shifts=("Net", "size"), Total=("Net", "sum"),
                          Hours=("Hours", "sum"))
    g["Avg shift"] = g["Total"] / g["Shifts"]
    g["Per hour"] = g["Total"] / g["Hours"].where(g["Hours"] > 0)
    g = g.reset_index().rename(columns={by: "Group"})
    if by == "Weekday":
        g["Group"] = [WEEKDAYS[int(i)] for i in g["Group"]]
    return g[cols].sort_values("Avg shift", ascending=False).reset_index(drop=True)


def ranked(d, n=5, best=True):
    """The n best (or worst) shifts by take-home, ignoring 0-hour rows."""
    d = d[d["Hours"] > 0]
    return d.sort_values("Net", ascending=not best).head(n)
