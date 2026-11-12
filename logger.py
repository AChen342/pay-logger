"""Google Sheets backend for Pay Logger.

Wraps a single Google Sheet ("Outback Pay Logging") with five tabs --
Daily, Weekly, Monthly, Yearly, Payday -- as pandas DataFrames. Daily is
the only source of truth; Weekly/Monthly/Yearly and the tip fields of
Payday are derived from it.

Loaded once per run: `Logger()` connects and pulls all five tabs into
DataFrames. Once it's told which days had a shift on the calendar
(`setShiftDates`), it rebuilds every derived row from Daily
(`recalculateAll`) -- and does so again after every add/edit/delete --
so totals always match the Daily logs.

A week/month/year is only totalled once it's over AND has no missing
entry (a calendar shift with no Daily log). Until the missing day is
logged, that period is left out of its tab, and a payday whose range
contains it keeps its previous numbers.

Every write method re-pushes its DataFrame back to the sheet
immediately; nothing is batched. Derived tabs are only rewritten when
their contents actually changed.
"""
import gspread
import numpy as np
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe

CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Outback Pay Logging"
MIN_WAGE = 17.65
# Paydays ending before this date predate tip tracking in this app; addPayDay
# zeroes out their tip-related fields instead of trying to reconstruct them.
LEGACY_CUTOFF = pd.Timestamp("2025-08-01")

TIP_COLS = ["Hours", "Card", "Cash", "Total Tip"]

# Extra per-shift details (added after the original five Daily columns, so
# older rows just have blanks). "Total Tip" is take-home: Card + Cash - Tip
# Out. Rows from before Tip Out existed have no tip-out, so their totals are
# unchanged.
DETAIL_COLS = ["Tip Out", "Shift Type", "Section", "Notes"]
DAILY_COLS = ["Date"] + TIP_COLS + DETAIL_COLS
SHIFT_TYPES = ("Lunch", "Dinner", "Double", "Other")

# The derived period tabs: (DataFrame attr, Worksheet attr, label column,
# label format, pandas period). Weeks run Monday-Sunday and are labelled
# by their Sunday ("Week Ending"); months/years by their first day.
PERIOD_TABS = (
    ("dfWeekly",  "weeklySheet",  "Week Ending", "%m/%d/%Y", "W-SUN"),
    ("dfMonthly", "monthlySheet", "Month",       "%m/%Y",    "M"),
    ("dfYearly",  "yearlySheet",  "Year",        "%Y",       "Y"),
)

# Payday columns derived from Daily (Start/End Date, Gross Pay and Tax are
# what you entered and are never changed by a recalculation).
PAYDAY_DERIVED = ["Total Hours", "Workday Pay", "Card Total", "Cash Total",
                  "Tip Total", "Before Taxes", "After Taxes",
                  "Hourly Wage (After Taxes)"]

class Logger():
    """Loads the sheet's five tabs and keeps Weekly/Monthly/Yearly rolled up
    from Daily. See the module docstring for the overall shape."""

    def __init__(self, shiftDates=None):
        """Load all five tabs. If `shiftDates` is given, also recalculate
        every derived row right away (see setShiftDates)."""
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sh = gc.open(SPREADSHEET_NAME)

        self.worksheet = sh.worksheet('Daily')
        self.df = self._withDetailCols(
            get_as_dataframe(self.worksheet).dropna(how='all'))

        self.weeklySheet = sh.worksheet('Weekly')
        self.dfWeekly = get_as_dataframe(self.weeklySheet).dropna(how='all')

        self.monthlySheet = sh.worksheet('Monthly')
        self.dfMonthly = get_as_dataframe(self.monthlySheet).dropna(how='all')

        self.yearlySheet = sh.worksheet('Yearly')
        self.dfYearly = get_as_dataframe(self.yearlySheet).dropna(how='all')

        self.payDaySheet = sh.worksheet('Payday')
        self.dfPayDay = get_as_dataframe(self.payDaySheet).dropna(how='all')

        # Bumped whenever any of the DataFrames changes, so screens can tell
        # whether what they last drew is still current (see App.stamp).
        self.version = 0

        # Dates (datetime.date) that had a shift on the calendar, or None if
        # unknown -- in which case nothing is recalculated, since a missing
        # entry couldn't be told apart from a day off.
        self.shiftDates = None
        if shiftDates is not None:
            self.setShiftDates(shiftDates)

    @staticmethod
    def _withDetailCols(df):
        """Make sure the Daily frame has every DAILY_COLS column (sheets
        made before shift details existed lack the new ones), in order,
        keeping any extra columns the sheet might have at the end."""
        df = df.copy()
        for c in DAILY_COLS:
            if c not in df.columns:
                df[c] = np.nan
        # gspread-dataframe can read stray empty columns as "Unnamed: N".
        extra = [c for c in df.columns
                 if c not in DAILY_COLS and not str(c).startswith("Unnamed")]
        return df[DAILY_COLS + extra]

    # --- Missing entries ---------------------------------------------

    def setShiftDates(self, shiftDates):
        """Tell the logger which days had a (started) shift on the
        calendar, then recalculate everything derived from Daily."""
        self.shiftDates = {pd.Timestamp(d).date() for d in shiftDates}
        self.recalculateAll()

    def loggedDates(self):
        """Set of dates (datetime.date) that have a Daily log."""
        if self.df.empty:
            return set()
        dates = pd.to_datetime(self.df["Date"], format="%m/%d/%Y", errors="coerce")
        return set(dates.dropna().dt.date)

    def missingDates(self):
        """Calendar shift dates with no Daily log, oldest first. Shifts
        from before the first Daily log predate this app and don't count."""
        if not self.shiftDates:
            return []
        logged = self.loggedDates()
        first = min(logged) if logged else None
        return sorted(d for d in self.shiftDates
                      if d not in logged and (first is None or d >= first))

    # --- Recalculation -----------------------------------------------

    def recalculateAll(self):
        """Rebuild Weekly/Monthly/Yearly from scratch and refresh the
        Payday tip totals, all from the current Daily logs. Each tab is
        only written back if something in it changed."""
        self.version = getattr(self, "version", 0) + 1
        if self.shiftDates is None:
            print("Shift dates unknown; skipping recalculation.")
            return

        missing = self.missingDates()
        if missing:
            print("Missing entries (periods containing these aren't totalled): "
                  + ", ".join(f"{d:%m/%d/%Y}" for d in missing))

        for dfAttr, sheetAttr, colName, dateFmt, period in PERIOD_TABS:
            new, skipped = self._buildPeriodTable(colName, dateFmt, period, missing)
            if skipped:
                print(f"{colName}: skipped {', '.join(skipped)} (missing entry)")
            old = getattr(self, dfAttr)
            if self._sameTable(old, new, colName, dateFmt, TIP_COLS):
                print(f"{colName}: up to date.")
                continue
            sheet = getattr(self, sheetAttr)
            set_with_dataframe(sheet, new, include_index=False, resize=True)
            setattr(self, dfAttr, new)
            print(f"{colName}: recalculated ({len(new)} rows).")

        self._recalculatePaydays(missing)

    def _dailyFrame(self):
        """Daily as a DataFrame with parsed dates and numeric tip columns."""
        d = self.df.copy()
        d["Date"] = pd.to_datetime(d["Date"], format="%m/%d/%Y", errors="coerce")
        d = d.dropna(subset=["Date"])
        for c in TIP_COLS + ["Tip Out"]:
            d[c] = pd.to_numeric(d.get(c), errors="coerce").fillna(0)
        return d

    def _buildPeriodTable(self, colName, dateFmt, period, missing):
        """Total Daily by week/month/year. Leaves out the period still in
        progress and any period containing a missing entry.

        Returns (table, skipped_labels)."""
        cols = [colName] + TIP_COLS
        d = self._dailyFrame()
        if d.empty:
            return pd.DataFrame(columns=cols), []

        d["Period"] = d["Date"].dt.to_period(period)
        agg = d.groupby("Period")[TIP_COLS].sum().sort_index()
        agg = agg[agg["Hours"] > 0]

        current = pd.Timestamp.now().to_period(period)
        missingPeriods = {pd.Timestamp(m).to_period(period) for m in missing}

        def label(p):
            ts = p.end_time.normalize() if period.startswith("W") else p.start_time
            return ts.strftime(dateFmt)

        skipped = [label(p) for p in agg.index if p < current and p in missingPeriods]
        keep = [p < current and p not in missingPeriods for p in agg.index]
        agg = agg[keep]

        table = agg.round(2).reset_index()
        table[colName] = [label(p) for p in table["Period"]]
        return table[cols].reset_index(drop=True), skipped

    def _paydayTotals(self, startDate, endDate, gross, tax):
        """The Daily-derived Payday fields for [startDate, endDate], or
        None if no hours were logged in that range."""
        d = self._dailyFrame()
        d = d[(d["Date"] >= startDate) & (d["Date"] <= endDate)]

        totalHours = round(d["Hours"].sum(), 2)
        if totalHours == 0:
            return None

        cardTotal = round(d["Card"].sum(), 2)
        cashTotal = round(d["Cash"].sum(), 2)
        tipOut    = round(d["Tip Out"].sum(), 2)
        totalTip  = round(cardTotal + cashTotal - tipOut, 2)
        beforeTax = round(totalTip + gross, 2)
        afterTax  = round(beforeTax - tax, 2)
        return {
            "Total Hours"               : totalHours,
            "Workday Pay"               : round(gross - tax, 2),
            "Card Total"                : cardTotal,
            "Cash Total"                : cashTotal,
            "Tip Total"                 : totalTip,
            "Before Taxes"              : beforeTax,
            "After Taxes"               : afterTax,
            "Hourly Wage (After Taxes)" : round(afterTax / totalHours, 2),
        }

    def _recalculatePaydays(self, missing):
        """Refresh each Payday row's tip/hours totals from Daily. Legacy
        rows, rows whose range has a missing entry, and rows with no
        logged hours in range are left exactly as they are."""
        if self.dfPayDay.empty:
            return

        updated = self.dfPayDay.copy()
        # Let whole-number columns read from the sheet take decimals.
        for col in PAYDAY_DERIVED:
            if col in updated.columns:
                updated[col] = updated[col].astype(object)
        missingTs = [pd.Timestamp(m) for m in missing]
        changed = False
        for idx, row in updated.iterrows():
            start = pd.to_datetime(row.get("Start Date"), errors="coerce")
            end   = pd.to_datetime(row.get("End Date"), errors="coerce")
            gross = pd.to_numeric(row.get("Gross Pay"), errors="coerce")
            tax   = pd.to_numeric(row.get("Tax"), errors="coerce")
            if pd.isna(start) or pd.isna(end) or pd.isna(gross) or pd.isna(tax):
                continue
            if end < LEGACY_CUTOFF:
                continue
            if any(start <= m <= end for m in missingTs):
                print(f"Payday {start:%m/%d/%Y}-{end:%m/%d/%Y}: skipped (missing entry)")
                continue
            fields = self._paydayTotals(start, end, float(gross), float(tax))
            if fields is None:
                continue
            for col, val in fields.items():
                cur = pd.to_numeric(row.get(col), errors="coerce")
                if pd.isna(cur) or not np.isclose(float(cur), val, atol=0.005):
                    updated.at[idx, col] = val
                    changed = True

        if changed:
            set_with_dataframe(self.payDaySheet, updated, include_index=False, resize=True)
            self.dfPayDay = updated
            print("Payday: recalculated.")
        else:
            print("Payday: up to date.")

    @staticmethod
    def _sameTable(old, new, colName, dateFmt, numCols):
        """True if `old` (as read from the sheet) already holds the same
        rows as `new`, ignoring formatting differences the sheet adds
        (e.g. "5/3/2026" vs "05/03/2026", 2025 vs "2025")."""
        if len(old) != len(new) or colName not in old.columns:
            return False
        if any(c not in old.columns for c in numCols):
            return False

        def norm(v):
            if isinstance(v, (int, float, np.integer, np.floating)) and not pd.isna(v):
                v = str(int(v))
            ts = pd.to_datetime(str(v), format=dateFmt, errors="coerce")
            if pd.isna(ts):
                ts = pd.to_datetime(str(v), errors="coerce")
            return None if pd.isna(ts) else ts.strftime(dateFmt)

        oldLabels = [norm(v) for v in old[colName]]
        if oldLabels != list(new[colName]):
            return False
        for c in numCols:
            a = pd.to_numeric(old[c], errors="coerce").to_numpy(dtype=float)
            b = new[c].to_numpy(dtype=float)
            if not np.allclose(a, b, atol=0.005, equal_nan=False):
                return False
        return True

    def sortByDate(self, df):
        """Return a copy of `df` sorted by its "Date" column (parsed as
        "%m/%d/%Y"), with "Date" restored to that same string format."""
        temp_df = df.copy()
        temp_df['Date'] = pd.to_datetime(temp_df['Date'], format="%m/%d/%Y")
        temp_df = temp_df.sort_values(by="Date")
        temp_df["Date"] = temp_df["Date"].dt.strftime("%m/%d/%Y")
        return temp_df

    @staticmethod
    def _entryRow(entry):
        """A shift entry -> one Daily-sheet row (dict keyed by column).

        `entry` is a dict with "date" ("%m/%d/%Y" string), "card", "cash",
        "hours" (floats) and optionally "tipOut" (float), "shiftType",
        "section", "notes" (strings). A plain (date, card, cash, hours)
        tuple -- the old shape -- is accepted too.
        """
        if not isinstance(entry, dict):
            day, card, cash, hours = entry
            entry = {"date": day, "card": card, "cash": cash, "hours": hours}
        card, cash = float(entry["card"]), float(entry["cash"])
        tipOut = float(entry.get("tipOut") or 0)
        blank = lambda v: (str(v).strip() or np.nan) if v is not None else np.nan
        return {
            "Date"       : entry["date"],
            "Hours"      : float(entry["hours"]),
            "Card"       : card,
            "Cash"       : cash,
            "Total Tip"  : round(card + cash - tipOut, 2),
            "Tip Out"    : tipOut,
            "Shift Type" : blank(entry.get("shiftType")),
            "Section"    : blank(entry.get("section")),
            "Notes"      : blank(entry.get("notes")),
        }

    def addTip(self, newEntry):
        """Add one Daily-sheet row (see _entryRow for `newEntry`) and write
        it back to the sheet."""
        new_row_df = pd.DataFrame([self._entryRow(newEntry)])
        updated_df = pd.concat([self.df, new_row_df], ignore_index=True)
        sorted_df = self.sortByDate(updated_df).reset_index(drop=True)

        set_with_dataframe(self.worksheet, sorted_df, include_index=False, resize=True)
        self.df = sorted_df
        self.recalculateAll()

    def editLog(self, index, newEntry):
        """Replace the Daily-sheet row at `index` (a self.df DataFrame
        index, as for deleteLog) with `newEntry` (same shape as addTip's)
        and write the result back to the sheet. The date may change, so
        the sheet is re-sorted by date afterwards.

        Weekly/Monthly/Yearly and Payday totals are recalculated
        afterwards (see recalculateAll).
        """
        row = self._entryRow(newEntry)
        df = self.df.copy()
        for col in ("Shift Type", "Section", "Notes"):
            df[col] = df[col].astype(object)
        for col, val in row.items():
            df.at[index, col] = val
        df = self.sortByDate(df).reset_index(drop=True)
        set_with_dataframe(self.worksheet, df, include_index=False, resize=True)
        self.df = df
        self.recalculateAll()

    def deleteLog(self, index):
        """Drop the Daily-sheet row at `index` (a self.df DataFrame index,
        not a display row number) and write the result back to the sheet."""
        self.df = self.df.drop(index).reset_index(drop=True)
        set_with_dataframe(self.worksheet, self.df, include_index=False, resize=True)
        self.recalculateAll()

    def addPayDay(self, newEntry):
        """Add one Payday-sheet row and write it back to the sheet.

        Totals (hours worked, card/cash tips, etc.) are computed by
        summing every Daily-sheet row whose date falls within
        [start, end], *except* when `end` is before LEGACY_CUTOFF -- those
        predate tip tracking in this app, so tip-related fields are zeroed
        out instead of summed.

        Args:
            newEntry: a (start, end, gross, tax) tuple, where start/end are
                datetimes and gross/tax are floats.
        """
        start, end, gross, tax = newEntry

        startDate = pd.Timestamp(start)
        endDate   = pd.Timestamp(end)
        startStr  = start.strftime("%m/%d/%Y")
        endStr    = end.strftime("%m/%d/%Y")

        workdayPay = round(gross - tax, 2)

        if endDate < LEGACY_CUTOFF:
            # Legacy entry: no tip data, zero everything tip-related
            newLog = {
                "Start Date"                : startStr,
                "End Date"                  : endStr,
                "Total Hours"               : 0,
                "Gross Pay"                 : gross,
                "Tax"                       : tax,
                "Workday Pay"               : workdayPay,
                "Card Total"                : 0,
                "Cash Total"                : 0,
                "Tip Total"                 : 0,
                "Before Taxes"              : gross,
                "After Taxes"               : workdayPay,
                "Hourly Wage (After Taxes)" : 0,
            }
        else:
            fields = self._paydayTotals(startDate, endDate, gross, tax)
            if fields is None:
                print("No hours found in date range — check your start/end dates.")
                return
            newLog = {
                "Start Date" : startStr,
                "End Date"   : endStr,
                "Gross Pay"  : gross,
                "Tax"        : tax,
                **fields,
            }
            newLog = {col: newLog[col] for col in (
                "Start Date", "End Date", "Total Hours", "Gross Pay", "Tax",
                "Workday Pay", "Card Total", "Cash Total", "Tip Total",
                "Before Taxes", "After Taxes", "Hourly Wage (After Taxes)")}

        new_row_df = pd.DataFrame([newLog])
        updated_dfPayDay = pd.concat([self.dfPayDay, new_row_df], ignore_index=True)

        set_with_dataframe(self.payDaySheet, updated_dfPayDay, include_index=False, resize=True)
        self.dfPayDay = updated_dfPayDay
        self.version = getattr(self, "version", 0) + 1
