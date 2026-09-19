# Pay Logger

A small desktop app for logging Outback Steakhouse shifts, tips, and
paydays straight into a Google Sheet ("Outback Pay Logging"), with a
dark, modern Tkinter GUI. `main.pyw` checks your Google Calendar for
today's shift (and its start time) and whether you've already logged
today before it even opens the window -- see "Running it" below.

## What it does

- **Add New Log** -- record a shift's card tips, cash tips, and hours. The
  date defaults to today and has a calendar picker.
- **View Logs** -- browse Daily/Weekly/Monthly/Yearly tip totals, and
  Payday history, in a searchable, sortable table. The **Tips** tab also
  has a **Graph View** (see below).
- **Edit / Delete Log** -- select a shift to change its date/card/cash/
  hours (popup form with a calendar), or to remove it.
- **Add Payday** -- record a paycheck; the app sums every shift in the
  date range to compute total tips, hours, and take-home pay. Start/end
  dates have calendar pickers, and the start date defaults to the day
  after your last payday's end date.

Every screen reads and writes through `logger.Logger`, which keeps five
tabs of the Google Sheet in sync: **Daily**, **Weekly**, **Monthly**,
**Yearly**, **Payday**. Weekly/Monthly/Yearly are rolled up from Daily
automatically on startup -- you never edit them directly.

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

### Calendar date pickers

Every date field has a calendar button: pick a day, or type it. The popup
has month (`‹` `›`) and year (`«` `»`) navigation and opens on the date
already in the field. It's built once shortly after startup and then only
shown/hidden, so it opens instantly (ttkbootstrap's own `DateEntry`
rebuilt its popup on every click, which was noticeably laggy).

## Project layout

```
plogger/
    main.pyw            Entry point (see "Running it" below).
    logger.py            Google Sheets backend: loads the 5 sheet tabs into
                          pandas DataFrames, aggregates Daily -> Weekly/
                          Monthly/Yearly, and pushes every add/edit/delete
                          back to the sheet.
    credentials.json     Google service-account credentials (not committed;
                          see "Setup" below).
    requirements.txt     Python dependencies.
    fonts/                Bundled Inter font files + license (see "Fonts").
    gui/                  The GUI, as a package:
        __init__.py       Re-exports App so `from gui import App` still
                          works from the outside.
        app.py            The App window: page navigation, and the
                          month/day/year/money input validators every
                          screen's date fields share. Starts maximized.
        pages.py          Page-name constants ("home", "new_log", ...)
                          screens navigate between, without needing to
                          import each other.
        fonts.py          Loads the bundled Inter font on Windows.
        formatting.py     Turns raw spreadsheet values into the display
                          strings tables show (date normalization, 2dp
                          money formatting, per-sheet row builders).
        widgets.py        Shared widgets: the page header bar, the
                          data-table widget (with this app's styling),
                          and the calendar pickers (CalendarButton,
                          DatePicker, fillDateBoxes).
        charts.py         The Tips graph's matplotlib figure and summary
                          numbers. Pure data -> figure, no Tk.
        tips_graph.py     The Tips graph panel (controls, summary tiles,
                          canvas, hover highlight/tooltip).
        screens/          One module per screen -- home.py, new_log.py,
                          view_logs.py, delete_logs.py (edit + delete),
                          new_payday.py. Each only depends on the shared
                          gui modules above, never on another screen, so
                          any one can be read and changed in isolation.
```

The GUI used to be one 600-line `gui.py`; it was split up without changing
what the app does -- read `gui/pages.py` for why screens are separate
files without circular imports, and `gui/formatting.py` for the row-
building logic that used to be copy-pasted across four screens.

## Setup

1. Install dependencies (includes matplotlib, used for the Tips graph):
   ```
   pip install -r requirements.txt
   ```
2. Place a Google service-account `credentials.json` in this folder, shared
   with edit access to a Google Sheet named **"Outback Pay Logging"**
   containing five tabs with these columns:
   - **Daily**: `Date, Hours, Card, Cash, Total Tip`
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
from a terminal). It checks Google Calendar for today's shift and its
start time, and whether you've already logged today. The GUI opens only
if there's a shift, it has started, and today isn't logged yet -- so once
your shift starts, every launch opens the app until you log your tips,
and after that launches exit quietly. (Launching before the shift starts
also exits without opening anything.)

To open the GUI directly regardless of those checks (e.g. for testing),
run:
```python
from gui import App
from logger import Logger
App(Logger()).mainloop()
```

## Design notes

- **Graph performance.** The chart canvas is created once and redrawn in
  place (rebuilding it flashed white). Hover only redraws the highlight box
  and tooltip over a cached render (blitting) instead of the whole figure,
  and the figure uses auto layout so margins re-fit on resize. A redraw is
  skipped when the view/metric/range didn't change.
- **Shift-time check.** `main.pyw` reads the calendar event's start time
  (earliest one if several, midnight for all-day events). Launched before
  it, the app exits without opening; from then on every launch opens until
  today's tips are logged.
- **Popups use plain `tk.Toplevel`.** ttkbootstrap's own `Toplevel` takes
  `title` as its first argument and differs between versions.

## Known limitations

- Editing or deleting a Daily log does not recalculate Weekly/Monthly/
  Yearly rows that were already rolled up, or Payday rows already added.
- Every add/edit/delete rewrites the whole Daily sheet, which will slow
  down as history grows.
- "View Logs" tables reload when you click a tab or toggle the graph, not
  live as logs are added on other screens.

## Fonts

The app bundles [Inter](https://rsms.me/inter/) (`fonts/Inter-Regular.ttf`,
`fonts/Inter-Bold.ttf`, SIL Open Font License in `fonts/OFL.txt`) and
registers it with Windows for this process only (`gui/fonts.py`, using the
`FR_PRIVATE` flag), so it renders correctly without installing anything
system-wide or needing admin rights. If the font files are missing, or
you're not on Windows, the app falls back to Segoe UI automatically.
