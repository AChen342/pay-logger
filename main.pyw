"""Entry point for Pay Logger.

Meant to be launched at login and/or repeatedly (e.g. by a scheduled task
double-clicking this .pyw file). It always opens the GUI (gui.App):

  * minimized to the taskbar when every recent shift is logged, and
  * as a normal (maximized) window when a shift on the Google Calendar has
    started but has no tip log yet -- today's, or any from the last
    LOOKBACK_DAYS days you forgot to log.

Only one copy runs at a time: launching again while it's open just exits
(or, with --open / dashboard.pyw, brings the open window to the front).
While it's open it re-checks the calendar every REFRESH_MINUTES and pops
the window up as soon as a shift needs logging.
"""
import os
import sys
import time
import traceback
import zoneinfo
from datetime import date, datetime, timedelta

# When launched at login (Startup folder / Task Scheduler) the working
# directory usually isn't this folder, so relative paths like
# "credentials.json" wouldn't be found. Always run from here.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

# A .pyw has no console, so print() output and crashes are invisible.
# Send them to pay_logger.log in this folder instead.
LOG_FILE = os.path.join(APP_DIR, "pay_logger.log")
if sys.stdout is None or not sys.stdout.isatty():
    _log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = _log
print(f"\n--- launched {datetime.now():%Y-%m-%d %H:%M:%S} ---")

WINDOW_TITLE = "Pay Logger"
_instance_mutex = None  # kept alive for the life of the process


def already_running():
    """True if another Pay Logger is already open (Windows only; elsewhere
    always False). Uses a named mutex, which Windows releases by itself
    when the process ends -- even after a crash."""
    global _instance_mutex
    if sys.platform != "win32":
        return False
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _instance_mutex = kernel32.CreateMutexW(None, False, "PayLogger.SingleInstance")
    return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


def show_running_window():
    """Restore the already-open Pay Logger window and bring it forward."""
    import ctypes
    user32 = ctypes.WinDLL("user32")
    hwnd = user32.FindWindowW(None, WINDOW_TITLE)
    if hwnd:
        user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)  # RESTORE / SHOW
        user32.SetForegroundWindow(hwnd)


if already_running():
    if "--open" in sys.argv[1:]:
        show_running_window()
    print("Already running. Exiting.")
    sys.exit(0)

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

import logger

try:
    from ui import App          # the Qt interface
except ImportError as e:        # PySide6 not installed
    print(f"Qt interface unavailable ({e}); using the old Tk one. "
          f"Run: pip install PySide6")
    from gui import App

CALENDAR_KEYWORD = "Hotschedules"
CREDENTIALS_FILE = "credentials.json"

# How far back to look for shifts you forgot to log. Shifts older than
# this are ignored, so an old gap in the sheet can't nag you forever.
LOOKBACK_DAYS = 14

# How often the open app re-checks the calendar for shifts to log.
REFRESH_MINUTES = 10

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar.readonly",
]

LOCAL_TZ = zoneinfo.ZoneInfo("America/New_York")


def get_calendar_shifts(first_day, last_day):
    """Start times (local datetimes) of every shift in Google Calendar from
    `first_day` through `last_day`, oldest first.

    An all-day event has no start time, so it counts as starting at
    midnight of its day.
    """
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=creds)

    time_min = datetime.combine(first_day, datetime.min.time(), tzinfo=LOCAL_TZ).isoformat()
    time_max = datetime.combine(last_day, datetime.max.time(), tzinfo=LOCAL_TZ).isoformat()

    # The range can span months, so follow nextPageToken until done.
    events = []
    page_token = None
    while True:
        events_result = service.events().list(
            calendarId="achen.w342@gmail.com",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
            pageToken=page_token,
        ).execute()
        events.extend(events_result.get("items", []))
        page_token = events_result.get("nextPageToken")
        if not page_token:
            break

    starts = []
    for event in events:
        title = event.get("summary", "")
        if CALENDAR_KEYWORD.lower() not in title.lower():
            continue
        start = event.get("start", {})
        if "dateTime" in start:
            start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone(LOCAL_TZ)
        elif "date" in start:  # all-day event: only a date
            start_dt = datetime.combine(date.fromisoformat(start["date"]), datetime.min.time(), tzinfo=LOCAL_TZ)
        else:
            continue
        if first_day <= start_dt.date() <= last_day:
            starts.append(start_dt)
    return sorted(starts)


def end_of_month(d):
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def logged_dates(log):
    """Returns the set of dates that already have a tip entry in the daily
    sheet."""
    if log.df.empty:
        return set()
    # Normalize sheet dates to date objects to avoid format mismatches
    # (e.g. Sheets may store "5/3/2026" but strftime produces "05/03/2026")
    sheet_dates = pd.to_datetime(log.df["Date"], format="%m/%d/%Y", errors="coerce").dt.date
    return set(sheet_dates.dropna())


# Right after boot/login, Wi-Fi often isn't connected yet, so the first
# Google calls fail. Keep retrying for a while before giving up.
STARTUP_RETRIES = 12
RETRY_DELAY_SECONDS = 15


def with_retries(fn, what):
    """Call fn(), retrying on any error (usually no network yet)."""
    for attempt in range(1, STARTUP_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == STARTUP_RETRIES:
                raise
            print(f"{what} failed ({type(e).__name__}: {e}); "
                  f"retrying in {RETRY_DELAY_SECONDS}s [{attempt}/{STARTUP_RETRIES}]")
            time.sleep(RETRY_DELAY_SECONDS)


def scan_calendar(log):
    """One calendar check. Returns a dict:
        all_shifts    set of dates with a shift that has started (since the
                      first Daily log, or the lookback window if earlier)
        recent_start  first day of the "nag" window (LOOKBACK_DAYS ago)
        upcoming      sorted dates of shifts that haven't started yet,
                      through the end of this week/month (for the forecast)
        shift_starts  date -> earliest start datetime (guesses Lunch/Dinner)
    """
    now = datetime.now(LOCAL_TZ)
    today = now.date()
    recent_start = today - timedelta(days=LOOKBACK_DAYS)
    first_day = min(logged_dates(log), default=recent_start)
    first_day = min(first_day, recent_start)
    last_day = max(end_of_month(today), today + timedelta(days=6 - today.weekday()))
    starts = get_calendar_shifts(first_day, last_day)
    shift_starts = {}
    for s in starts:
        shift_starts.setdefault(s.date(), s)
    return {
        "all_shifts": {s.date() for s in starts if s <= now and s.date() <= today},
        "recent_start": recent_start,
        "upcoming": sorted({s.date() for s in starts if s > now}),
        "shift_starts": shift_starts,
    }


def main(show=False):
    """Recalculate totals, then open the app: minimized if every recent
    shift is logged, as a normal window if one needs logging or `show` is
    set (dashboard.pyw / `main.pyw --open`)."""
    log = with_retries(logger.Logger, "Loading the sheet")
    scan = with_retries(lambda: scan_calendar(log), "Calendar check")

    # Recalculates Weekly/Monthly/Yearly and Payday from Daily on every
    # launch.
    with_retries(lambda: log.setShiftDates(scan["all_shifts"]), "Recalculating totals")

    # Only nag about shifts in the last LOOKBACK_DAYS days.
    missed = sorted(d for d in scan["all_shifts"]
                    if d >= scan["recent_start"] and d not in logged_dates(log))
    if missed:
        print("Unlogged shifts: " + ", ".join(f"{d:%m/%d/%Y}" for d in missed))
    else:
        print("All recent shifts are logged." + ("" if show else " Opening minimized."))

    App(log, missedDates=missed, upcomingShifts=scan["upcoming"],
        shiftStarts=scan["shift_starts"],
        startMinimized=not missed and not show,
        rescan=lambda: scan_calendar(log),
        rescanMinutes=REFRESH_MINUTES).mainloop()

if __name__=="__main__":
    try:
        main(show="--open" in sys.argv[1:])
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise
