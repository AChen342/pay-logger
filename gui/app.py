"""The application window: page navigation and the shared input validators
every screen's date/money fields use.

Building the actual page contents is left to gui.screens -- this module
only owns what's genuinely shared across all of them: the ttkbootstrap
Window itself, the Google Sheets logger handed down to every screen as
`self.logger`, and the four `validatecommand` callbacks (month/day/year/
money) that every date and money Entry in the app is wired up to.
"""
import os
import sys
import threading
from datetime import date, datetime

import pandas as pd
import ttkbootstrap as ttk

import goals
import logger
from . import fonts, pages
from .screens.home import HomeScreen
from .screens.insights import Insights
from .screens.new_log import NewLog
from .screens.view_logs import ViewLogs
from .screens.delete_logs import DeleteLogs
from .screens.new_payday import NewPayDay

THEME = "darkly"

# Which screen class backs each page name (see gui.pages for why pages are
# looked up by string rather than by importing the screen classes directly
# everywhere).
_PAGES = {
    pages.HOME: HomeScreen,
    pages.NEW_LOG: NewLog,
    pages.VIEW_LOGS: ViewLogs,
    pages.DELETE_LOGS: DeleteLogs,
    pages.NEW_PAYDAY: NewPayDay,
    pages.INSIGHTS: Insights,
}


class App(ttk.Window):
    """The Pay Logger window.

    Builds one frame per page up front (stacked on top of each other with
    `grid`), then shows/hides them with `tkraise` as the user navigates --
    so switching screens is instant and every screen keeps its state
    (typed-but-not-submitted form fields, table contents, etc.) while it's
    hidden.
    """

    # Fonts are computed once in gui.fonts (Inter if it could be bundled
    # and registered, Segoe UI otherwise) and exposed here under the names
    # every screen already expects: master.FONT, master.FONT_BOLD, etc.
    FONT_FAMILY = fonts.FAMILY
    FONT_BIG = fonts.BIG
    FONT_TITLE = fonts.TITLE
    FONT_HEAD = fonts.HEAD
    FONT_BOLD = fonts.BOLD
    FONT = fonts.BODY
    FONT_SMALL = fonts.SMALL

    def __init__(self, log=None, missedDates=None, upcomingShifts=None,
                 shiftStarts=None, startMinimized=False, rescan=None,
                 rescanMinutes=10):
        super().__init__(themename=THEME)
        self.logger = log if log is not None else logger.Logger()
        # Shift dates main.pyw found with no tip log (today's and any
        # missed earlier ones), oldest first. See unloggedDates().
        self.missedDates = sorted(missedDates or [])
        # Shifts on the calendar that haven't started yet (through the end
        # of this month), for the Dashboard's forecast. None = the calendar
        # wasn't checked (e.g. App opened directly), so the forecast falls
        # back to your recent pace.
        self.upcomingShifts = upcomingShifts
        # date -> calendar start datetime, so Add Shift can guess
        # Lunch/Dinner for the day being logged.
        self.shiftStarts = shiftStarts or {}
        self.goals = goals.load()
        # Bumped when something screens draw from changes outside the
        # logger (goals, calendar re-check). See stamp().
        self._uiVersion = 0

        self.title("Pay Logger")
        self._setIcon()
        self.geometry("1120x820")
        self.minsize(940, 680)
        # Start maximized (title bar stays, so the window can still be
        # restored/closed normally).
        self.state("zoomed")

        # A softer, roomier feel for the base (uncolored) widgets: text
        # entries get a bit more interior breathing room instead of hugging
        # the typed text tightly.
        ttk.Style().configure("TEntry", padding=(8, 8))

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Validation commands, shared by every date/money Entry across all
        # screens. Tk needs each callback registered once (self.register)
        # and then referenced by the token it returns.
        self.monthCmd = (self.register(self.checkMonth), "%P")
        self.dayCmd = (self.register(self.checkDay), "%P")
        self.yearCmd = (self.register(self.checkYear), "%P")
        self.moneyCmd = (self.register(self.checkMoney), "%P")

        self.frames = {}
        for pageId, PageClass in _PAGES.items():
            frame = PageClass(self)
            self.frames[pageId] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.showFrame(pages.HOME)

        if startMinimized:
            self.iconify()  # restoring it brings back the maximized window

        # Background calendar re-check (see _startRescan). `rescan` is
        # main.pyw's scan_calendar; None = no re-checking.
        self._rescan = rescan
        self._rescanMs = int(rescanMinutes * 60 * 1000)
        self._rescanThread = None
        self._rescanResult = None
        if rescan is not None:
            self.after(self._rescanMs, self._startRescan)
        self.after(1200, self._warmUp)

    def stamp(self):
        """Changes whenever anything a screen draws from could have changed
        (logs, paydays, goals, calendar, the date). Screens remember the
        stamp they last drew with and skip redrawing when it's the same --
        that's what makes switching screens instant."""
        return (getattr(self.logger, "version", 0), self._uiVersion, self.today())

    def _warmUp(self):
        """Shortly after startup, draw the slow-to-build screens (the
        matplotlib charts) once in the background, one per idle moment, so
        the first click on them doesn't stall."""
        steps = [self.frames[pages.INSIGHTS].refresh,
                 self.frames[pages.VIEW_LOGS].graph.refresh]

        def run():
            if not steps:
                return
            try:
                steps.pop(0)()
            except Exception as e:
                print(f"Warm-up step failed ({type(e).__name__}: {e})")
            self.after(150, run)
        run()

    def _setIcon(self):
        """Use pay_logger.ico for the window and taskbar (Windows). Without
        its own AppUserModelID the taskbar would show Python's icon."""
        ico = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "pay_logger.ico")
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PayLogger")
            self.iconbitmap(default=ico)
        except Exception:
            pass  # missing file / not Windows: keep the default icon

    def showFrame(self, page):
        """Raise the frame registered for `page` (one of the gui.pages
        constants) to the top of the window's stack, then call its
        `onShow()` hook if it has one.

        (A `<Map>` binding can't be used for this: every frame is gridded
        once at startup and only restacked with tkraise afterwards, so
        `<Map>` fires once and never again.)"""
        self._page = page
        frame = self.frames[page]
        frame.tkraise()
        onShow = getattr(frame, "onShow", None)
        if onShow is not None:
            onShow()

    def unloggedDates(self):
        """The shift dates from `missedDates` that still have no tip log
        (so the list shrinks as you log them), oldest first."""
        if not self.missedDates:
            return []
        df = self.logger.df
        logged = set()
        if not df.empty:
            logged = set(pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce").dt.date.dropna())
        return [d for d in self.missedDates if d not in logged]

    # --- Background calendar re-check ---------------------------------
    # The app stays open (usually minimized) for days, so every few
    # minutes it asks the calendar again. The network call runs on a
    # thread so the window never freezes; Tk is only touched from the main
    # thread (_pollRescan), since Tk isn't thread-safe.
    def _startRescan(self):
        def work():
            try:
                self._rescanResult = self._rescan()
            except Exception as e:  # offline, asleep, etc. -- try again later
                print(f"Calendar re-check failed ({type(e).__name__}: {e})")
        self._rescanResult = None
        self._rescanThread = threading.Thread(target=work, daemon=True)
        self._rescanThread.start()
        self.after(500, self._pollRescan)

    def _pollRescan(self):
        if self._rescanThread.is_alive():
            self.after(500, self._pollRescan)
            return
        try:
            if self._rescanResult is not None:
                self._applyRescan(self._rescanResult)
        except Exception as e:
            print(f"Applying calendar re-check failed ({type(e).__name__}: {e})")
        self.after(self._rescanMs, self._startRescan)

    def _applyRescan(self, scan):
        """Take a fresh scan_calendar() result: recalculate totals if the
        set of worked days changed, update the reminders/forecast, and pop
        the window up if a new shift needs logging."""
        before = set(self.unloggedDates())
        if scan["all_shifts"] != self.logger.shiftDates:
            self.logger.setShiftDates(scan["all_shifts"])
        logged = self.logger.loggedDates()
        new = (sorted(d for d in scan["all_shifts"]
                      if d >= scan["recent_start"] and d not in logged),
               scan["upcoming"], scan["shift_starts"])
        if new != (self.missedDates, self.upcomingShifts, self.shiftStarts):
            self.missedDates, self.upcomingShifts, self.shiftStarts = new
            self._uiVersion += 1
        self.showFrame(self._page)  # redraws only if something changed
        if set(self.missedDates) - before:
            self.deiconify()
            self.state("zoomed")
            self.lift()

    def today(self):
        return date.today()

    def setGoals(self, newGoals):
        """Save goals to goals.json and refresh the Dashboard."""
        self.goals = dict(newGoals)
        goals.save(self.goals)
        self._uiVersion += 1
        self.frames[pages.HOME].onShow()

    # --- Validation --------------------------------------------------
    # These back the `validatecommand` on every date/money Entry in the
    # app: Tk calls the matching one on every keystroke with the field's
    # value-so-far (`%P`), and rejects the keystroke if it returns False.
    def checkMonth(self, v):
        if v == "":
            return True
        if not v.isdigit() or len(v) > 2:
            return False
        return 1 <= int(v) <= 12

    def checkDay(self, v):
        if v == "":
            return True
        if not v.isdigit() or len(v) > 2:
            return False
        return 1 <= int(v) <= 31

    def checkYear(self, v):
        if v == "":
            return True
        return v.isdigit() and len(v) <= 4

    def checkMoney(self, v):
        if v == "":
            return True
        if v.count(".") > 1:
            return False
        try:
            float(v)
        except ValueError:
            return False
        if "." in v and len(v.split(".")[1]) > 2:
            return False
        return True

    def validateFullDate(self, month, day, year):
        """Parse a month/day/year Entry trio into a datetime, or None if
        it doesn't form a real calendar date."""
        try:
            return datetime.strptime(f"{month}/{day}/{year}", "%m/%d/%Y")
        except ValueError:
            return None
