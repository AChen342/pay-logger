"""Google Calendar sync, shared by the desktop launcher and the web server.

Reads Hotschedules shifts from the calendar with the same service account
that writes the sheet, and works out which days are logged, which recent
shifts are missing, and which shifts are still upcoming (for the forecast).

No Qt and no top-level side effects, so it imports cleanly anywhere.
"""
import os
import time
import zoneinfo
from datetime import date, datetime, timedelta

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

CALENDAR_ID = "achen.w342@gmail.com"
CALENDAR_KEYWORD = "Hotschedules"
CREDENTIALS_FILE = os.environ.get("PAYLOGGER_CREDENTIALS", "credentials.json")
LOOKBACK_DAYS = 14
LOCAL_TZ = zoneinfo.ZoneInfo("America/New_York")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def get_calendar_shifts(first_day, last_day):
    """Start times (local datetimes) of every Hotschedules shift from
    `first_day` through `last_day`, oldest first."""
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)

    time_min = datetime.combine(first_day, datetime.min.time(), tzinfo=LOCAL_TZ).isoformat()
    time_max = datetime.combine(last_day, datetime.max.time(), tzinfo=LOCAL_TZ).isoformat()

    events, page_token = [], None
    while True:
        result = service.events().list(
            calendarId=CALENDAR_ID, timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy="startTime", maxResults=2500,
            pageToken=page_token).execute()
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    starts = []
    for event in events:
        if CALENDAR_KEYWORD.lower() not in event.get("summary", "").lower():
            continue
        start = event.get("start", {})
        if "dateTime" in start:
            when = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone(LOCAL_TZ)
        elif "date" in start:
            when = datetime.combine(date.fromisoformat(start["date"]),
                                    datetime.min.time(), tzinfo=LOCAL_TZ)
        else:
            continue
        if first_day <= when.date() <= last_day:
            starts.append(when)
    return sorted(starts)


def end_of_month(d):
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def logged_dates(log):
    """Dates that already have a Daily tip entry."""
    if log.df.empty:
        return set()
    sheet_dates = pd.to_datetime(log.df["Date"], format="%m/%d/%Y", errors="coerce").dt.date
    return set(sheet_dates.dropna())


def scan_calendar(log):
    """One calendar check. Returns all_shifts / recent_start / upcoming /
    shift_starts (see the desktop launcher for the full description)."""
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


def with_retries(fn, what, retries=12, delay=15):
    """Call fn(), retrying on any error (usually no network yet at boot)."""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == retries:
                raise
            print(f"{what} failed ({type(e).__name__}: {e}); "
                  f"retrying in {delay}s [{attempt}/{retries}]")
            time.sleep(delay)
