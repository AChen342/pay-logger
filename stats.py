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
    d["Weekday"] = d["Date"].dt.day_of_week
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


def describe_days(days):
    """[3, 4, 5, 6] -> "Thu-Sun"; [1, 3, 5] -> "Tue, Thu, Sat"."""
    days = sorted(set(days or ()))
    if not days:
        return ""
    short = [WEEKDAYS[i][:3] for i in days]
    if len(days) > 2 and days == list(range(days[0], days[-1] + 1)):
        return f"{short[0]}-{short[-1]}"
    return ", ".join(short)


def _likely_dates(today, end, workdays, covered_through):
    """Dates in (covered_through, end] that fall on a usual workday.

    What the schedule will probably hold once the manager posts it. Only
    the stretch past the last posted shift is filled in -- gaps inside a
    posted week are the schedule, not an omission."""
    if not workdays:
        return []
    first = max(today, covered_through) + timedelta(days=1)
    out, day = [], first
    while day <= end:
        if day.weekday() in workdays:
            out.append(day)
        day += timedelta(days=1)
    return out


def forecast(d, today, upcoming=None, start=None, end=None, workdays=(),
             unlogged=()):
    """Project where the period [start, end] (default: this month) will end
    up in take-home tips.

    Three kinds of shift make up the projection:
      * `scheduled` -- on the calendar and still to come.
      * `unlogged`  -- already worked, no tips logged yet (otherwise they
                       fall through the gap between "earned" and "to come").
      * `likely`    -- not posted yet, but on a day the user says they
                       usually work. Only past the last posted shift.

    `upcoming` is the calendar's future shift dates, or None if the
    calendar wasn't checked -- then the remainder is guessed from recent
    pace, unless usual workdays are set.

    Each shift is valued at the recent average for its weekday (or the
    overall recent average, for weekdays with few samples). The low/high
    range scales the unearned part by a typical slow (25th percentile) and
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
    workdays = set(workdays or ())

    logged = set(d["Date"].dt.date)
    pending = sorted({u for u in (unlogged or ())
                      if start <= u <= end and u not in logged})

    if upcoming is not None:
        scheduled = sorted({u for u in upcoming
                            if (u > today or (u == today and u not in logged))
                            and start <= u <= end})
        source = "calendar"
    else:
        scheduled = [] if workdays else _pace_shift_dates(d, today, end)
        source = "calendar" if workdays else "pace"

    known = set(scheduled) | set(pending)
    covered_through = max(known) if known else today
    likely = [day for day in _likely_dates(today, end, workdays, covered_through)
              if day not in known]

    value = lambda days: sum(by_day.get(day.weekday(), overall) for day in days)
    scheduled_value = value(scheduled) + value(pending)
    likely_value = value(likely)
    expected = scheduled_value + likely_value
    scale_lo = p25 / overall if overall > 0 else 1.0
    scale_hi = p75 / overall if overall > 0 else 1.0
    return {
        "so_far": so_far["net"],
        "projected": so_far["net"] + expected,
        "low": so_far["net"] + expected * scale_lo,
        "high": so_far["net"] + expected * scale_hi,
        "scheduled": scheduled,
        "pending": pending,
        "likely": likely,
        "scheduled_value": scheduled_value,
        "likely_value": likely_value,
        "remaining": scheduled + pending,   # everything already known about
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


# --- Holidays -------------------------------------------------------------
# A small built-in table (no external package). Each entry is a greeting
# and, where the pattern is well known for a casual steakhouse, a note on
# how the day tends to run against a normal shift -- so the forecast can
# admit it's probably off rather than quietly predicting an ordinary day.
# "tends" is a general-knowledge lean, not a promise.

def _nth_weekday(year, month, weekday, n):
    """Date of the n-th `weekday` (0=Monday) of a month, e.g. the 2nd
    Sunday of May."""
    from calendar import Calendar
    days = [d for d in Calendar().itermonthdates(year, month)
            if d.month == month and d.weekday() == weekday]
    return days[n - 1]


def _last_weekday(year, month, weekday):
    from calendar import Calendar
    days = [d for d in Calendar().itermonthdates(year, month)
            if d.month == month and d.weekday() == weekday]
    return days[-1]


def _holiday_table(year):
    """{date: (greeting, note, lean)} for one year. lean is 'up', 'down',
    'closed' or None -- how the day usually runs vs a normal shift."""
    from datetime import date as _date, timedelta as _td
    thanksgiving = _nth_weekday(year, 11, 3, 4)   # 4th Thursday
    table = {
        _date(year, 1, 1):   ("Happy New Year!", "usually a bit busier than normal", "up"),
        _date(year, 2, 14):  ("Happy Valentine's Day!", "casual spots often run normal or quieter — the fancy places get the rush", "down"),
        _date(year, 3, 17):  ("Happy St. Patrick's Day!", None, None),
        _nth_weekday(year, 5, 6, 2): ("Happy Mother's Day!", "one of the busiest serving days of the year", "up"),
        _last_weekday(year, 5, 0):   ("Happy Memorial Day!", None, None),
        _nth_weekday(year, 6, 6, 3): ("Happy Father's Day!", "usually well above a normal day", "up"),
        _date(year, 7, 4):   ("Happy 4th of July!", None, None),
        _nth_weekday(year, 9, 0, 1): ("Happy Labor Day!", None, None),
        _date(year, 10, 31): ("Happy Halloween!", "usually slower — people are out trick-or-treating", "down"),
        thanksgiving - _td(days=1): ("", "the night before Thanksgiving is one of the busiest bar nights", "up"),
        thanksgiving:        ("Happy Thanksgiving!", "most locations are closed", "closed"),
        _date(year, 12, 24): ("Merry Christmas Eve!", None, None),
        _date(year, 12, 25): ("Merry Christmas!", "most locations are closed", "closed"),
        _date(year, 12, 31): ("Happy New Year's Eve!", "casual dining often runs quieter", "down"),
    }
    return table


def holiday(when):
    """{greeting, note, lean} for a date that lands on a known holiday, or
    None. lean: 'up' / 'down' / 'closed' / None."""
    if when is None:
        return None
    when = pd.Timestamp(when).date()
    entry = _holiday_table(when.year).get(when)
    if entry is None:
        return None
    greeting, note, lean = entry
    return {"greeting": greeting, "note": note, "lean": lean}


# --- Next-shift prediction ------------------------------------------------
# Tuned on real history: a 120-day window beat 60, 90, 365 and all-time, and
# the 5th-95th percentiles of the sample turned out to cover about three
# quarters of shifts (small samples understate the spread). Rather than
# claim a number, prediction_accuracy() below measures what the range
# actually catches, so the app can say so.

PREDICT_WINDOW_DAYS = 120
PREDICT_LO, PREDICT_HI = 0.05, 0.95
MIN_PREDICT_SAMPLES = 4


def _predict_basis(d, when, window=PREDICT_WINDOW_DAYS):
    """(rows, scale, how) -- the past shifts a prediction for `when` is
    learned from, a multiplier, and a phrase describing them.

    Narrowest first: this weekday recently; then this weekday ever, scaled
    by how much the job pays now against its whole history (a thin weekday
    like a Monday still has a shape worth keeping, it's just stale); then
    any recent shift; then everything. The scaling step was worth about $8
    a shift on the weekdays that need it, measured against real history."""
    when = pd.Timestamp(when)
    past = d[(d["Date"] < when) & (d["Hours"] > 0)]
    if past.empty:
        return past, 1.0, ""
    cut = when - timedelta(days=window)
    weekday = int(when.day_of_week)
    day_name = WEEKDAYS[weekday]
    months = round(window / 30)

    same = past[(past["Weekday"] == weekday) & (past["Date"] >= cut)]
    if len(same) >= MIN_PREDICT_SAMPLES:
        return same, 1.0, f"{day_name}s over the last {months} months"

    recent = past[past["Date"] >= cut]
    ever = past[past["Weekday"] == weekday]
    if len(ever) >= MIN_PREDICT_SAMPLES and len(recent) >= 2 * MIN_PREDICT_SAMPLES:
        overall = past["Net"].median()
        scale = (recent["Net"].median() / overall) if overall > 0 else 1.0
        return ever, float(scale), f"every {day_name} you have logged, at your recent pace"

    if len(recent) >= 2 * MIN_PREDICT_SAMPLES:
        return recent, 1.0, f"your last {len(recent)} shifts"
    return past, 1.0, "all your shifts"


def predict_shift(d, when, hours=None):
    """What one shift on `when` is likely to bring in take-home tips:
    {mid, lo, hi, basis, samples}, or None without enough history.

    `hours` sharpens it when the shift length is known (it then predicts a
    rate per hour), but a Hotschedules calendar entry only carries a start
    time, so the dashboard asks without it."""
    rows, scale, how = _predict_basis(d, when)
    if len(rows) < 3:
        return None
    if hours and hours > 0:
        values = (rows["Net"] / rows["Hours"]) * hours
    else:
        values = rows["Net"]
    return {"date": when,
            "mid": float(values.median() * scale),
            "lo": float(values.quantile(PREDICT_LO) * scale),
            "hi": float(values.quantile(PREDICT_HI) * scale),
            "basis": how, "samples": int(len(rows))}


def prediction_accuracy(d, n=60):
    """How well predict_shift would have done on the last `n` shifts, each
    predicted from only what came before it: {n, median_err, within_50,
    coverage}. None if there isn't enough history to say.

    This is the honest half of the feature -- it lets the app show how far
    off it usually is instead of asking to be trusted."""
    rows = d[d["Hours"] > 0].reset_index(drop=True)
    if len(rows) < 40:
        return None
    errors, inside = [], 0
    for i in range(max(len(rows) - n, 20), len(rows)):
        row = rows.iloc[i]
        guess = predict_shift(rows.iloc[:i], row["Date"])
        if guess is None:
            continue
        errors.append(abs(guess["mid"] - row["Net"]))
        inside += int(guess["lo"] <= row["Net"] <= guess["hi"])
    if len(errors) < 15:
        return None
    errors = np.array(errors)
    return {"n": len(errors), "median_err": float(np.median(errors)),
            "within_50": float((errors <= 50).mean()),
            "coverage": inside / len(errors)}


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
