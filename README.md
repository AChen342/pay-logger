# Pay Logger

A small desktop app for logging Outback Steakhouse shifts, tips, and
paydays straight into a Google Sheet ("Outback Pay Logging"), with a
dark, modern Qt (PySide6) interface. `main.pyw` opens it minimized, and pops the
window up whenever a shift on your Google Calendar has started but isn't
logged yet -- including days you missed -- see "Running it" below.

## What it does

- **Dashboard** (home screen, ServerLife-style) -- this week / month / year
  so far (take-home, shifts, hours, $/hr), progress bars toward your income
  goals, a **month-end forecast**, and your latest shifts with notes.
- **Add Shift** -- record a shift's card tips, cash tips, tip-out, hours,
  shift type (Lunch/Dinner/Double/Other), section, and notes, with a live
  take-home and $/hr readout. The date defaults to the next unlogged shift
  (or today), and the shift type is pre-picked from the calendar shift's
  start time (before 3pm = Lunch).
- **Next shift** (Dashboard) -- what the next shift on your calendar is
  likely to bring, as a range, with the prediction's own track record
  beside it.
- **Insights** -- for the last 30/90 days, this year, or all time: average
  take-home per shift by weekday (chart), tables by shift type and by
  section, and your best and slowest shifts.
- **Goals** (Dashboard button) -- weekly / monthly / yearly take-home
  targets, saved in `goals.json` next to the app (not in the sheet).
- **View Logs** -- browse Daily/Weekly/Monthly/Yearly tip totals, and
  Payday history, in a searchable, sortable table. The **Tips** tab also
  has a **Graph View** (see below).
- **Edit / Delete Log** -- select a shift to change any of its fields
  (same form as Add Shift, in a popup), or to remove it.
- **Add Payday** -- record a paycheck; the app sums every shift in the
  date range to compute total tips, hours, and take-home pay. Start/end
  dates have calendar pickers, and the start date defaults to the day
  after your last payday's end date.

Every screen reads and writes through `logger.Logger`, which keeps five
tabs of the Google Sheet in sync: **Daily**, **Weekly**, **Monthly**,
**Yearly**, **Payday**. Weekly/Monthly/Yearly (and the tip/hours totals
on Payday rows) are recalculated from Daily on every launch and after
every add/edit/delete -- you never edit them directly.

### Take-home and tip-outs

"Take-home" everywhere is Card + Cash - Tip Out, and that's what the Daily
sheet's **Total Tip** now stores (so Weekly/Monthly/Yearly and Payday tip
totals are net of tip-outs too). Leave Tip Out blank/0 if the card number
you enter is already after the tip pool. Older rows have no tip-out, so
their totals don't change.

### Forecast

The month-end forecast is what you've made so far this month plus a value
for each shift still left: your average take-home for that weekday over
the last 120 days (or your overall average, for weekdays with fewer than 3
shifts). The "likely" range uses your typical slow (25th percentile) and
good (75th percentile) shift. Remaining shifts come from your Google
Calendar through the end of the month; if the app was opened without the
calendar check, they're estimated from how often you've worked lately.
With a monthly goal set, it tells you whether you're on track or roughly
how many extra shifts you'd need to pick up. The week and year cards show
an "on pace for" figure the same way.

### Predicting one shift

The Dashboard estimates the next scheduled shift from your own history.
It looks for the same weekday over the last 120 days; if that weekday is
thin lately it falls back to every one of those weekdays you have logged,
scaled by how much the job pays now against its whole history; failing
that, your recent shifts. The figure is the median of that group and the
range its 5th-95th percentiles.

It is shown as a range on purpose, with `stats.prediction_accuracy()`
beside it: that re-runs the prediction across your last 60 shifts, each
predicted from only what came before it, and reports how far off it
usually was and how often reality landed inside the range. The app says
that out loud rather than asking to be trusted.

Measured on 294 real shifts, the model missed by about $37 in a typical
shift (against $48 for "your average shift") and its range held about
three quarters of the time. Knowing the shift length would cut the miss
to about $33, but a Hotschedules calendar entry is a 5-minute marker --
it carries a start time, not a duration -- so the Dashboard predicts
without it. `predict_shift(..., hours=...)` takes one when it is known.

Window length, fallback order and the percentile band were all picked by
backtesting against real history, not by taste.

### Missing entries

A **missing entry** is a day with a "Hotschedules" shift on your calendar
that has started but has no Daily log (shifts before your first Daily log
don't count). A week, month or year is only totalled once it's over *and*
has no missing entry -- until then it's left out of its tab. Likewise, a
Payday whose date range contains a missing entry keeps its old numbers.
As soon as you log the missing day, everything fills in. The missing
dates and skipped periods are written to `pay_logger.log` on each launch.

### Tips graph (View Logs -> Tips -> Graph View)

- **View by** Day / Week / Month / Year, and **Show** Total tips or Tips
  per hour (tips divided by hours worked).
- **From / To** date range with calendar pickers; defaults to January 1st
  of this year through today. **Reset range** returns to that default.
- **Summary tiles** for the chosen range: total tips, average per shift,
  average per hour, hours worked, and best day.
- Bars are stacked card + cash. Hovering a bar highlights it and shows a
  tooltip (total or per-hour figure, card/cash split, hours). The tooltip
  flips sides so it never runs off the chart.

### Date fields

Every date field is a Qt date box: type it, or click the arrow for a
calendar popup.

### The interface

The screens live in `ui/` and are built with **PySide6** (Qt). Every page
is built once at startup and kept in a stack, so switching screens is a
raise rather than a rebuild -- that's what makes it feel instant. A page
only redraws when the data behind it changed: `App.stamp()` is a small
tuple (logger version, UI version, today's date) that each screen
remembers from its last draw.

The old Tkinter interface is still in `gui/`, and `main.pyw` falls back to
it automatically if PySide6 isn't installed. Both read exactly the same
`logger`, `stats`, `charts` and `formatting` modules, so neither can drift
from the other's numbers. Delete `gui/` if you don't want the fallback.

Saving a shift, an edit, a delete or a payday writes the whole Daily tab
back to Google Sheets, which takes a few seconds, so those run on a
background thread: the button shows "Saving…", the window stays usable,
and the result ("Saved ✓" or an error) appears when it's done. The
calendar re-check runs the same way.

## Project layout

```
plogger/
    main.pyw            Entry point (see "Running it" below).
    dashboard.pyw        Opens the app regardless (main.pyw --open).
    stats.py             Dashboard/Insights math: period totals, forecast,
                          next-shift prediction and its self-scoring, goal
                          progress, breakdowns. Pure pandas.
    goals.py             Loads/saves goals.json (income goals).
    logger.py            Google Sheets backend: loads the 5 sheet tabs into
                          pandas DataFrames, aggregates Daily -> Weekly/
                          Monthly/Yearly, and pushes every add/edit/delete
                          back to the sheet.
    credentials.json     Google service-account credentials (not committed;
                          see "Setup" below).
    requirements.txt     Python dependencies.
    fonts/                Bundled Inter font files + license (see "Fonts").
    charts.py            Matplotlib figures (tips bars, weekday averages).
                          No GUI toolkit in it, so both interfaces use it.
    formatting.py        Raw sheet values -> the strings tables show.
    ui/                   The Qt interface (see "The interface" above):
        theme.py          Colors, fonts, and the app-wide stylesheet.
        widgets.py        Cards, stat tiles, the sortable/searchable table,
                          money and date inputs, the shift form, the chart
                          canvas.
        pages.py          Page-name constants used to navigate.
        app.py            The window: page stack, shared state, background
                          saving, the calendar re-check.
        screens/          dashboard.py, add_shift.py, view_logs.py (+
                          tips_graph.py), insights.py, edit_logs.py,
                          add_payday.py, dialogs.py, base.py.
    gui/                  The old Tkinter interface, kept as a fallback
                          (same screens, same data modules; charts.py and
                          formatting.py here are now one-line shims
                          re-exporting the top-level versions).
```

Nothing in `ui/` or `gui/` works anything out: the numbers all come from
`logger.py` (what's in the sheet), `stats.py` (totals, forecast, goals,
breakdowns) and `charts.py` (the figures), which is why a second interface
could be added without touching any of them.

## Setup

1. Install dependencies (PySide6 for the interface, matplotlib for the
   charts):
   ```
   pip install -r requirements.txt
   ```
   If you'd rather install just the new piece: `pip install PySide6`.
2. Place a Google service-account `credentials.json` in this folder, shared
   with edit access to a Google Sheet named **"Outback Pay Logging"**
   containing five tabs with these columns:
   - **Daily**: `Date, Hours, Card, Cash, Total Tip`, then `Tip Out,
     Shift Type, Section, Notes` (the app adds these four itself the
     first time it saves if they're missing; older rows stay blank)
   - **Weekly**: `Week Ending, Hours, Card, Cash, Total Tip`
   - **Monthly**: `Month, Hours, Card, Cash, Total Tip`
   - **Yearly**: `Year, Hours, Card, Cash, Total Tip`
   - **Payday**: `Start Date, End Date, Total Hours, Gross Pay, Tax,
     Workday Pay, Card Total, Cash Total, Tip Total, Before Taxes,
     After Taxes, Hourly Wage (After Taxes)`
3. `main.pyw` also checks Google Calendar for a shift (looking for an
   event containing "Hotschedules" in its title) using the same
   `credentials.json`, so that service account needs calendar read access
   too if you use that feature.

## Running it

Double-click `main.pyw` (or run `pythonw main.pyw` / `python main.pyw`
from a terminal), or have Windows launch it at login. It always opens:

- **minimized to the taskbar** when every shift from the last 14 days
  (`LOOKBACK_DAYS` in `main.pyw`) is logged, and
- **as a normal window** when a shift that has already started has no tip
  log -- today's, or one you missed.

While it's open it re-checks the calendar every 10 minutes
(`REFRESH_MINUTES`) and pops the window up as soon as a shift needs
logging, so it can sit minimized for days. Only one copy runs at a time:
launching `main.pyw` again while it's open does nothing.

To bring the window up yourself, click it on the taskbar or double-click
**`dashboard.pyw`** (same as `main.pyw --open`), which opens it un-minimized
or brings the already-open window to the front.

**Desktop icon:** double-click `Create Desktop Shortcut.bat` once to put a
"Pay Logger" icon (`pay_logger.ico`) on your Desktop that runs
`dashboard.pyw`. Re-run it if you move this folder.

**Laptops:** if it's started by Task Scheduler, untick *Conditions -> "Start
the task only if the computer is on AC power"* (on by default), or it won't
launch on battery.

When it opens because of unlogged shifts, the Dashboard lists them, and
**Add Shift** defaults its date to the oldest one; after each submit it
moves on to the next, then back to today once you're caught up.

To open the GUI directly regardless of those checks (e.g. for testing),
run:
```python
from gui import App
from logger import Logger
App(Logger()).mainloop()
```

## Design notes

- **Switching screens.** Pages are built once into a `QStackedWidget` and
  only raised afterwards, and each one redraws only when `App.stamp()`
  changes. The two chart screens are also drawn once in the background a
  second after startup (`App._warm_up`), so the first click on them doesn't
  stall either.
- **Graph performance.** The chart canvas is created once and redrawn in
  place. Hover only redraws the highlight box and tooltip over a cached
  render (blitting) instead of the whole figure, and the figure uses auto
  layout so margins re-fit on resize. A redraw is skipped when the
  view/metric/range didn't change.
- **Styling.** All of it is one stylesheet in `ui/theme.py`; widgets opt
  into a look with a dynamic property (`variant="success"`), never with
  their own stylesheet. Note that only windows paint the page background --
  a blanket `QWidget { background: ... }` rule would also repaint the
  inside of every card, and the card's ID selector would then outweigh the
  button styles.
- **Shift-time check.** `main.pyw` reads each calendar event's start time
  (midnight for all-day events). A shift counts once it has started; every
  started shift in the lookback window without a Daily log makes the app
  open un-minimized. Gaps older than `LOOKBACK_DAYS` are ignored so an old hole in
  the sheet can't nag forever.
- **Threads.** Qt widgets are only ever touched on the main thread:
  `App.run_task` runs the work on a worker thread and hands the result back
  through a signal (`taskFinished`), which Qt queues onto the UI thread.

## Known limitations

- If you had a shift on the calendar but didn't actually work it (called
  out, cut before clocking in), that day counts as missing forever and
  blocks its week/month/year. Log it with 0 tips/hours to clear it.
- Every add/edit/delete rewrites the whole Daily sheet, which will slow
  down as history grows.
- Saving is still as slow as Google Sheets is; it just no longer freezes
  the window.
- Editing or deleting is blocked while another save is in flight only by
  the buttons being disabled -- don't run two copies of the app against the
  same sheet at once.

## Fonts

The app bundles [Inter](https://rsms.me/inter/) (`fonts/Inter-Regular.ttf`,
`fonts/Inter-Bold.ttf`, SIL Open Font License in `fonts/OFL.txt`) and
loads it straight into Qt at startup (`ui/theme.py`), so it renders
correctly without installing anything
system-wide or needing admin rights. If the font files are missing, or
you're not on Windows, the app falls back to Segoe UI automatically.
