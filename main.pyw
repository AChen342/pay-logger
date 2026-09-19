"""Entry point for Pay Logger.

Meant to be launched repeatedly (e.g. by a scheduled task double-clicking
this .pyw file). It only opens the GUI (gui.App) when all of these hold:

  1. today has a shift on the Google Calendar,
  2. that shift has started (launches before the start time just exit), and
  3. no tip log has been submitted today yet.

So from the moment a shift starts, every launch opens the app until you
log that day's tips; after that, launches exit without opening anything.
"""
import sys
import zoneinfo
from datetime import datetime

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

import logger
from gui import App

CALENDAR_KEYWORD = "Hotschedules"
CREDENTIALS_FILE = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar.readonly",
]

LOCAL_TZ = zoneinfo.ZoneInfo("America/New_York")


def get_shift_start():
    """Returns when today's shift starts (a timezone-aware datetime), or
    None if today has no shift in Google Calendar.

    If there are several matching events today, the earliest start is
    used. An all-day event has no start time, so it counts as starting at
    midnight (i.e. the app may open any time that day).
    """
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=creds)

    today_local = datetime.now(LOCAL_TZ).date()

    time_min = datetime.combine(today_local, datetime.min.time(), tzinfo=LOCAL_TZ).isoformat()
    time_max = datetime.combine(today_local, datetime.max.time(), tzinfo=LOCAL_TZ).isoformat()

    events_result = service.events().list(
        calendarId="achen.w342@gmail.com",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    starts = []
    for event in events_result.get("items", []):
        title = event.get("summary", "")
        if CALENDAR_KEYWORD.lower() not in title.lower():
            continue
        start = event.get("start", {})
        if "dateTime" in start:
            starts.append(datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone(LOCAL_TZ))
        else:  # all-day event: only a date
            starts.append(datetime.combine(today_local, datetime.min.time(), tzinfo=LOCAL_TZ))

    return min(starts) if starts else None

def already_logged_today(log):
    """Returns True if a tip entry for today already exists in the daily sheet."""
    if log.df.empty:
        return False
    # Normalize sheet dates to date objects to avoid format mismatches
    # (e.g. Sheets may store "5/3/2026" but strftime produces "05/03/2026")
    today = datetime.now().date()
    sheet_dates = pd.to_datetime(log.df["Date"], format="%m/%d/%Y", errors="coerce").dt.date
    return today in sheet_dates.values

def main():
    # Check Google Calendar for today's shift and when it starts
    shift_start = get_shift_start()
    if shift_start is None:
        logger.Logger()
        sys.exit(0)

    if datetime.now(LOCAL_TZ) < shift_start:
        print(f"Shift starts at {shift_start:%I:%M %p}; not opening yet.")
        logger.Logger()
        sys.exit(0)

    log = logger.Logger()

    if already_logged_today(log):
        print("Tip already logged for today. Exiting.")
        sys.exit(0)

    App(log).mainloop()

if __name__=="__main__":
    main()
