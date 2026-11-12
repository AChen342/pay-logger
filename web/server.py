"""Pay Logger as a web app -- the same data and forecast code as the
desktop, served over HTTP so it opens on a phone.

Everything substantive is reused untouched: logger (the Google Sheet),
stats (totals, forecast, next-shift prediction, holidays), goals and
calsync (the calendar). This module is only the HTTP layer: it keeps one
Logger in memory, refreshes it and the calendar in the background, and
turns each screen into a JSON endpoint. The browser (static/) draws it.

Run:  uvicorn web.server:app --host 0.0.0.0 --port 8690
"""
import os
import sys
import threading
from datetime import date, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# The app's own modules live one level up; make them importable whether the
# server is started as "web.server" or from inside web/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calsync
import goals
import logger
import stats

# Keep goals.json on a writable data volume in the container.
goals.GOALS_FILE = os.environ.get("PAYLOGGER_GOALS", goals.GOALS_FILE)

REFRESH_MINUTES = int(os.environ.get("PAYLOGGER_REFRESH_MINUTES", "10"))
_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="Pay Logger")


class Store:
    """One shared Logger plus the latest calendar scan, guarded by a lock
    so a background refresh never overlaps a request mid-write."""

    def __init__(self):
        self.lock = threading.RLock()
        self.logger = None
        self.scan = {"all_shifts": set(), "upcoming": [], "shift_starts": {},
                     "recent_start": date.today()}
        self.ready = False
        self.error = None

    def load(self):
        """(Re)read the sheet and the calendar. Safe to call repeatedly."""
        try:
            log = calsync.with_retries(logger.Logger, "Loading the sheet", retries=1)
            scan = calsync.with_retries(lambda: calsync.scan_calendar(log),
                                        "Calendar check", retries=1)
            log.setShiftDates(scan["all_shifts"])
            with self.lock:
                self.logger, self.scan = log, scan
                self.ready, self.error = True, None
        except Exception as e:
            with self.lock:
                self.error = f"{type(e).__name__}: {e}"
            print(f"Load failed ({self.error})")

    def reload_sheet(self):
        """Re-read just the sheet (after our own write) without a calendar
        round-trip."""
        with self.lock:
            scan = self.scan
        log = logger.Logger()
        log.setShiftDates(scan["all_shifts"])
        with self.lock:
            self.logger = log


store = Store()


def _bg_refresh():
    import time
    while True:
        time.sleep(REFRESH_MINUTES * 60)
        store.load()


@app.on_event("startup")
def _startup():
    threading.Thread(target=store.load, daemon=True).start()
    threading.Thread(target=_bg_refresh, daemon=True).start()


def _require():
    if not store.ready:
        raise HTTPException(503, store.error or "Still loading the sheet…")
    return store.logger


def _today():
    return date.today()


# --- Read endpoints -------------------------------------------------------

@app.get("/api/state")
def state():
    """Everything the dashboard shows."""
    with store.lock:
        if not store.ready:
            return {"ready": False, "error": store.error}
        log, scan = store.logger, store.scan
    g = goals.load()
    workdays = goals.load_workdays()
    today = _today()
    d = stats.shifts(log.df)

    logged = calsync.logged_dates(log)
    missed = sorted(x for x in scan["all_shifts"]
                    if x >= scan["recent_start"] and x not in logged)
    upcoming = scan["upcoming"]

    periods = {}
    fcs = {}
    for key in ("weekly", "monthly", "yearly"):
        a, b = stats.PERIODS[key](today)
        t = stats.totals(stats.between(d, a, b))
        fc = stats.forecast(d, today, None if key == "yearly" else upcoming, a, b,
                            workdays=() if key == "yearly" else workdays,
                            unlogged=missed)
        gp = stats.goal_progress(g.get(key), t["net"],
                                 fc["projected"] if fc else None,
                                 fc["per_shift"] if fc else None)
        periods[key] = {"start": a.isoformat(), "end": b.isoformat(),
                        "net": t["net"], "shifts": t["shifts"], "hours": t["hours"],
                        "per_hour": t["per_hour"], "goal": g.get(key),
                        "progress": gp}
        fcs[key] = fc

    # Next shift
    nxt = None
    when = upcoming[0] if upcoming else None
    guess = stats.predict_shift(d, when) if when else None
    if guess:
        start = scan["shift_starts"].get(when)
        nxt = {"date": when.isoformat(),
               "clock": _clock(start),
               "mid": guess["mid"], "lo": guess["lo"], "hi": guess["hi"],
               "basis": guess["basis"], "samples": guess["samples"],
               "accuracy": stats.prediction_accuracy(d),
               "holiday": _holiday_payload(stats.holiday(when), when)}

    recent = [_recent_row(r) for _, r in d.tail(8).iloc[::-1].iterrows()]
    return {
        "ready": True,
        "today": today.isoformat(),
        "greeting": (stats.holiday(today) or {}).get("greeting", ""),
        "missed": [x.isoformat() for x in missed],
        "periods": periods,
        "forecast": _forecast_payload(fcs["monthly"], g.get("monthly"), workdays),
        "next_shift": nxt,
        "recent": recent,
        "settings": {"weekly": g.get("weekly"), "monthly": g.get("monthly"),
                     "yearly": g.get("yearly"), "workdays": workdays},
    }


def _clock(start):
    if not start or not (start.hour or start.minute):
        return ""
    hour = start.hour % 12 or 12
    return f"{hour}:{start.minute:02d} {'am' if start.hour < 12 else 'pm'}"


def _holiday_payload(hol, when):
    if not hol:
        return None
    lean = {"up": f"likely busier than a normal {when:%A} — this may read low",
            "down": f"often slower than a normal {when:%A} — this may read high",
            "closed": "most locations are closed"}.get(hol["lean"])
    return {"greeting": hol["greeting"], "note": lean}


def _forecast_payload(fc, goal, workdays):
    if fc is None:
        return None
    gp = stats.goal_progress(goal, fc["so_far"], fc["projected"], fc["per_shift"])
    return {
        "projected": fc["projected"], "low": fc["low"], "high": fc["high"],
        "so_far": fc["so_far"], "source": fc["source"],
        "scheduled": len(fc["scheduled"]), "scheduled_value": fc["scheduled_value"],
        "pending": len(fc["pending"]),
        "likely": len(fc["likely"]), "likely_value": fc["likely_value"],
        "likely_days": stats.describe_days(workdays),
        "upcoming": [x.isoformat() for x in fc["scheduled"][:6]],
        "goal": goal, "goal_progress": gp,
    }


def _recent_row(r):
    note = r["Notes"]
    if r["Section"]:
        note = f"Section {r['Section']}" + (f" · {note}" if note else "")
    return {"date": r["Date"].strftime("%a %m/%d"), "type": r["Type"],
            "net": float(r["Net"]),
            "per_hour": float(r["Net"] / r["Hours"]) if r["Hours"] > 0 else None,
            "note": note}


@app.get("/api/logs")
def logs(tab: str = "tips"):
    log = _require()
    import formatting as fmt
    if tab == "tips":
        rev = log.df[::-1]
        return {"headers": fmt.TIP_HEADERS, "rows": fmt.tip_rows(rev),
                "indices": [int(i) for i in rev.index]}
    if tab == "payday":
        headers = ["Start", "End", "Hours", "Gross", "Tax", "Work Pay", "Card",
                   "Cash", "Tips", "Before Tax", "After Tax", "Hourly"]
        return {"headers": headers, "rows": fmt.payday_rows(log.dfPayDay[::-1])}
    period = {"weekly": ("dfWeekly", "Week Ending", "%m/%d/%Y"),
              "monthly": ("dfMonthly", "Month", "%m/%Y"),
              "yearly": ("dfYearly", "Year", "%Y")}.get(tab)
    if not period:
        raise HTTPException(404, "unknown tab")
    attr, col, dfmt = period
    df = getattr(log, attr)
    return {"headers": [col, "Hours", "Card", "Cash", "Take-home"],
            "rows": fmt.period_rows(df[::-1], col, dfmt)}


@app.get("/api/insights")
def insights(range: str = "Last 90 days"):
    log = _require()
    d = stats.between(stats.shifts(log.df), *_range_bounds(range))
    t = stats.totals(d)
    groups = {}
    for key in ("Type", "Section"):
        g = stats.breakdown(d, key)
        groups[key] = [{"group": r["Group"], "shifts": int(r["Shifts"]),
                        "avg": r["Avg shift"],
                        "per_hour": None if r["Per hour"] != r["Per hour"] else r["Per hour"]}
                       for _, r in g.iterrows()]
    weekday = [{"group": r["Group"], "avg": r["Avg shift"], "shifts": int(r["Shifts"])}
               for _, r in stats.breakdown(d, "Weekday").iterrows()]
    rank = lambda best: [{"date": r["Date"].strftime("%a %m/%d"), "type": r["Type"],
                          "net": float(r["Net"]),
                          "per_hour": float(r["Net"] / r["Hours"]) if r["Hours"] > 0 else None}
                         for _, r in stats.ranked(d, 5, best).iterrows()]
    untagged = int(((d["Type"] == "") & (d["Hours"] > 0)).sum())
    return {"tiles": {"net": t["net"], "shifts": t["shifts"],
                      "per_shift": t["per_shift"], "per_hour": t["per_hour"]},
            "weekday": weekday, "groups": groups,
            "best": rank(True), "worst": rank(False), "untagged": untagged}


@app.get("/api/tips_series")
def tips_series(view: str = "Day", metric: str = "Total tips",
                start: str = "", end: str = ""):
    log = _require()
    d = stats.shifts(log.df)
    s = _parse(start) or (d["Date"].min().date() if not d.empty else _today())
    e = _parse(end) or _today()
    series = stats.tips_series(d, view, s, e, metric)
    series["summary"] = _summary_payload(stats.summary(log.df, s, e))
    return series


def _summary_payload(st):
    if st is None:
        return None
    return {"total": st["total"], "hours": st["hours"], "shifts": st["shifts"],
            "avg_shift": st["avg_shift"], "avg_hour": st["avg_hour"],
            "best_amount": st["best_amount"],
            "best_date": st["best_date"].strftime("%m/%d/%y")}


def _range_bounds(choice):
    from datetime import timedelta
    today = _today()
    if choice == "Last 30 days":
        return today - timedelta(days=29), today
    if choice == "Last 90 days":
        return today - timedelta(days=89), today
    if choice == "This year":
        return today.replace(month=1, day=1), today
    return None, None


def _parse(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@app.get("/api/settings")
def get_settings():
    g = goals.load()
    return {"weekly": g.get("weekly"), "monthly": g.get("monthly"),
            "yearly": g.get("yearly"), "workdays": goals.load_workdays()}


# --- Write endpoints ------------------------------------------------------

class ShiftIn(BaseModel):
    date: str
    card: float
    cash: float
    hours: float
    tipOut: float = 0.0
    shiftType: str = ""
    section: str = ""
    notes: str = ""


class PaydayIn(BaseModel):
    start: str
    end: str
    gross: float
    tax: float


class SettingsIn(BaseModel):
    weekly: float | None = None
    monthly: float | None = None
    yearly: float | None = None
    workdays: list[int] = []


def _entry(s: ShiftIn):
    when = _parse(s.date)
    if when is None:
        raise HTTPException(400, "bad date")
    return {"date": when.strftime("%m/%d/%Y"), "card": s.card, "cash": s.cash,
            "hours": s.hours, "tipOut": s.tipOut, "shiftType": s.shiftType,
            "section": s.section, "notes": s.notes}


@app.post("/api/shift")
def add_shift(s: ShiftIn):
    log = _require()
    with store.lock:
        log.addTip(_entry(s))
    return {"ok": True}


@app.put("/api/shift/{index}")
def edit_shift(index: int, s: ShiftIn):
    log = _require()
    with store.lock:
        if index not in log.df.index:
            raise HTTPException(409, "that row changed — reload and try again")
        log.editLog(index, _entry(s))
    return {"ok": True}


@app.delete("/api/shift/{index}")
def delete_shift(index: int):
    log = _require()
    with store.lock:
        if index not in log.df.index:
            raise HTTPException(409, "that row changed — reload and try again")
        log.deleteLog(index)
    return {"ok": True}


@app.post("/api/payday")
def add_payday(p: PaydayIn):
    log = _require()
    s, e = _parse(p.start), _parse(p.end)
    if s is None or e is None or e < s:
        raise HTTPException(400, "bad dates")
    with store.lock:
        log.addPayDay((datetime.combine(s, datetime.min.time()),
                       datetime.combine(e, datetime.min.time()), p.gross, p.tax))
    return {"ok": True}


@app.post("/api/settings")
def set_settings(s: SettingsIn):
    goals.save({"weekly": s.weekly, "monthly": s.monthly, "yearly": s.yearly})
    goals.save_workdays(s.workdays)
    return {"ok": True}


@app.post("/api/refresh")
def refresh():
    store.load()
    return {"ok": store.ready, "error": store.error}


# --- Static frontend (mounted last so it doesn't shadow /api) -------------

@app.get("/")
def index():
    return FileResponse(os.path.join(_STATIC, "index.html"))


app.mount("/", StaticFiles(directory=_STATIC), name="static")
