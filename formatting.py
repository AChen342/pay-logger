"""Turns raw spreadsheet values into the display strings the tables show,
plus the row-tuple builders every screen shares.

Pure pandas -- no GUI toolkit -- so both the Qt UI (`ui/`) and the old Tk
one (`gui/`) use the same formatting.
"""
from datetime import datetime

import pandas as pd


def fmt(v):
    """Format a value as a 2dp float, or as a plain string if it isn't
    numeric."""
    try:
        return f"{float(v):.2f}"
    except (ValueError, TypeError):
        return str(v)


def fmtDate(v, fmt="%m/%d/%Y"):
    """Normalize a date-like value to a consistent display format.

    Rows added by this app are always plain "%m/%d/%Y" strings, but older
    rows entered directly into the spreadsheet (before a column existed
    here, or typed in by hand) can come back from Google Sheets as real
    date/datetime values instead of text, or as text in a different
    format. Left alone, those render inconsistently (e.g. a stray
    "2026-09-01 00:00:00" next to "09/01/2026"). This coerces anything
    date-shaped to the same look everywhere.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime(fmt)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return s
        try:
            return pd.to_datetime(s).strftime(fmt)
        except (ValueError, TypeError):
            return s
    return str(v)


# --- Row builders --------------------------------------------------------
# Every screen that shows a table of tip logs, period totals, or paydays
# needs the same raw DataFrame row turned into the same tuple of display
# strings. Centralizing that here means the formatting has only one place
# to be right -- and one place to fix, the day the sheet's columns change.

# Columns every tip-log table shows (Add Shift, View Logs, Edit/Delete).
TIP_HEADERS = ["Date", "Type", "Hours", "Card", "Cash", "Tip Out",
               "Take-home", "Section", "Notes"]


def money(v, cents=True):
    """$1,234.56 (or $1,235 with cents=False)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"${v:,.2f}" if cents else f"${v:,.0f}"


def text(v):
    """A sheet cell as display text ('' for blanks/NaN)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def num(v):
    """A sheet cell as a float (0 for blanks)."""
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else f
    except (TypeError, ValueError):
        return 0.0


def parse_date(v, fmt="%m/%d/%Y"):
    """A sheet cell as a datetime.date, or None if it isn't date-shaped."""
    s = fmtDate(v, fmt)
    try:
        return datetime.strptime(s, fmt).date()
    except (ValueError, TypeError):
        return None


def tip_row(r):
    """One Daily-sheet row -> TIP_HEADERS display strings. Take-home is
    Card + Cash - Tip Out; rows from before shift details existed just
    show blanks for Type/Section/Notes."""
    hours = num(r.get('Hours'))
    net = num(r.get('Card')) + num(r.get('Cash')) - num(r.get('Tip Out'))
    return (fmtDate(r['Date']), text(r.get('Shift Type')), fmt(hours),
            fmt(num(r.get('Card'))), fmt(num(r.get('Cash'))),
            fmt(num(r.get('Tip Out'))), fmt(net),
            text(r.get('Section')), text(r.get('Notes')))


def tip_rows(df):
    """tip_row() applied to every row of a Daily-sheet DataFrame."""
    return [tip_row(r) for _, r in df.iterrows()]


def period_row(r, col_name, date_format="%m/%d/%Y"):
    """One Weekly/Monthly/Yearly-sheet row -> (<period>, Hours, Card, Cash,
    Total Tip).

    `col_name` is whichever column holds the period label ("Week Ending",
    "Month", or "Year"); `date_format` controls how it's displayed (a week
    ending is a full date, a month is "%m/%Y", a year is just "%Y").
    """
    return (fmtDate(r[col_name], date_format), fmt(r['Hours']), fmt(r['Card']), fmt(r['Cash']), fmt(r['Total Tip']))


def period_rows(df, col_name, date_format="%m/%d/%Y"):
    """period_row() applied to every row of a Weekly/Monthly/Yearly-sheet
    DataFrame."""
    return [period_row(r, col_name, date_format) for _, r in df.iterrows()]


def payday_row(r):
    """One Payday-sheet row -> the 12-column tuple ViewLogs' Payday tab and
    NewPayDay's "Recent Paydays" table both show."""
    return (
        fmtDate(r['Start Date']), fmtDate(r['End Date']), fmt(r['Total Hours']),
        fmt(r['Gross Pay']), fmt(r['Tax']), fmt(r['Workday Pay']),
        fmt(r['Card Total']), fmt(r['Cash Total']), fmt(r['Tip Total']),
        fmt(r['Before Taxes']), fmt(r['After Taxes']), fmt(r['Hourly Wage (After Taxes)']),
    )


def payday_rows(df):
    """payday_row() applied to every row of a Payday-sheet DataFrame."""
    return [payday_row(r) for _, r in df.iterrows()]
