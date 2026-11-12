"""The application window: the page stack, the shared state every screen
reads, and the two things that must not freeze the window -- saving to
Google Sheets and re-checking the calendar.

Pages are built once and stacked (QStackedWidget), so switching screens is
just a raise: no rebuilding, no repaint of a whole window of widgets. Each
screen redraws only when `stamp()` changes (see below).
"""
import os
import sys
import threading
import traceback

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

import goals
import logger
from . import pages, theme
from .screens.add_payday import AddPayday
from .screens.add_shift import AddShift
from .screens.dashboard import Dashboard
from .screens.edit_logs import EditLogs
from .screens.insights import Insights
from .screens.view_logs import ViewLogs

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PAGES = (
    (pages.HOME, Dashboard),
    (pages.ADD_SHIFT, AddShift),
    (pages.VIEW_LOGS, ViewLogs),
    (pages.INSIGHTS, Insights),
    (pages.EDIT_LOGS, EditLogs),
    (pages.ADD_PAYDAY, AddPayday),
)


class App(QMainWindow):
    """The Pay Logger window.

    Takes the same arguments as the old Tk window, so `main.pyw` doesn't
    care which one it opened.
    """

    # Emitted (from a worker thread) when a background job finishes:
    # (callback, result, error).
    taskFinished = Signal(object, object, object)

    def __init__(self, log=None, missedDates=None, upcomingShifts=None,
                 shiftStarts=None, startMinimized=False, rescan=None,
                 rescanMinutes=10):
        qapp = QApplication.instance() or QApplication(sys.argv)
        theme.load_fonts()
        qapp.setStyleSheet(theme.stylesheet())
        super().__init__()
        self._qapp = qapp

        self.logger = log if log is not None else logger.Logger()
        # Shift dates main.pyw found with no tip log (today's and any
        # missed earlier ones), oldest first. See unlogged_dates().
        self.missedDates = sorted(missedDates or [])
        # Shifts on the calendar that haven't started yet, for the
        # forecast. None = the calendar wasn't checked, so the forecast
        # falls back to recent pace.
        self.upcomingShifts = upcomingShifts
        # date -> calendar start time, so Add Shift can guess Lunch/Dinner.
        self.shiftStarts = shiftStarts or {}
        self.goals = goals.load()
        # Bumped when something screens draw from changes outside the
        # logger (goals, calendar re-check). See stamp().
        self._uiVersion = 0

        self.setWindowTitle("Pay Logger")  # main.pyw finds the window by this
        self.resize(1440, 920)
        self.setMinimumSize(1100, 720)
        icon = os.path.join(_APP_DIR, "pay_logger.ico")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))
        if sys.platform == "win32":
            try:  # without this the taskbar shows Python's icon
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PayLogger")
            except Exception:
                pass

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.frames = {}
        for name, PageClass in _PAGES:
            frame = PageClass(self)
            self.frames[name] = frame
            self.stack.addWidget(frame)
        self._page = pages.HOME
        self.show_page(pages.HOME)

        self.taskFinished.connect(self._task_finished)

        if startMinimized:
            self.showMinimized()
        else:
            self.showMaximized()

        # Background calendar re-check (main.pyw's scan_calendar).
        self._rescan = rescan
        self._rescanMs = max(1, int(rescanMinutes * 60 * 1000))
        if rescan is not None:
            QTimer.singleShot(self._rescanMs, self._start_rescan)
        QTimer.singleShot(1200, self._warm_up)

    # --- State every screen reads ---------------------------------------
    def stamp(self):
        """Changes whenever anything a screen draws from could have changed
        (logs, paydays, goals, calendar, the date). Screens remember the
        stamp they last drew with and skip redrawing when it's unchanged."""
        return (getattr(self.logger, "version", 0), self._uiVersion, self.today())

    @staticmethod
    def today():
        from datetime import date
        return date.today()

    def unlogged_dates(self):
        """The dates from `missedDates` that still have no tip log (so the
        list shrinks as they're logged), oldest first."""
        if not self.missedDates:
            return []
        logged = self.logger.loggedDates()
        return [d for d in self.missedDates if d not in logged]

    def set_goals(self, new_goals):
        """Save goals to goals.json and redraw."""
        self.goals = dict(new_goals)
        goals.save(self.goals)
        self._uiVersion += 1
        self.show_page(self._page)

    # --- Navigation -------------------------------------------------------
    def show_page(self, name):
        """Raise a page and let it refresh itself if its data changed."""
        self._page = name
        frame = self.frames[name]
        self.stack.setCurrentWidget(frame)
        on_show = getattr(frame, "on_show", None)
        if on_show is not None:
            on_show()

    def _warm_up(self):
        """Draw the slow-to-build chart screens once in the background, one
        per tick, so the first click on them is instant too.

        Skipped while the window is minimized (how the app starts when
        nothing needs logging): the widgets have no size then, and drawing
        a chart into nothing fails -- on Windows with "OSError: [Errno 22]
        Invalid argument". It retries until the window is open."""
        if self.isMinimized() or not self.isVisible():
            QTimer.singleShot(10_000, self._warm_up)
            return

        steps = [self.frames[pages.INSIGHTS].refresh,
                 self.frames[pages.VIEW_LOGS].warm_up]

        def run():
            if not steps:
                return
            try:
                steps.pop(0)()
            except Exception:
                print("Warm-up step failed:")
                traceback.print_exc()
            QTimer.singleShot(120, run)

        run()

    # --- Background work --------------------------------------------------
    # Writing to Google Sheets takes seconds, and the calendar check needs
    # the network, so both run on a worker thread. Qt widgets are only
    # touched back on the main thread, in _task_finished.
    def run_task(self, work, on_done=None):
        """Run `work()` off the UI thread, then call `on_done(result,
        error)` back on it. The window stays responsive meanwhile."""
        def runner():
            try:
                self.taskFinished.emit(on_done, work(), None)
            except Exception as e:
                self.taskFinished.emit(on_done, None, e)

        threading.Thread(target=runner, daemon=True).start()

    def _task_finished(self, on_done, result, error):
        if on_done is not None:
            on_done(result, error)
        elif error is not None:
            print(f"Background task failed ({type(error).__name__}: {error})")

    def busy(self, on):
        """Show (or clear) the wait cursor over the whole window."""
        if on:
            self._qapp.setOverrideCursor(Qt.CursorShape.BusyCursor)
        else:
            self._qapp.restoreOverrideCursor()

    # --- Calendar re-check ------------------------------------------------
    def _start_rescan(self):
        self.run_task(self._rescan, self._apply_rescan)

    def _apply_rescan(self, scan, error):
        """Take a fresh scan_calendar() result: recalculate totals if the
        worked days changed, refresh the screens, and pop the window up if
        a new shift needs logging."""
        QTimer.singleShot(self._rescanMs, self._start_rescan)
        if error is not None or scan is None:
            print(f"Calendar re-check failed ({type(error).__name__}: {error})")
            traceback.print_exception(type(error), error, error.__traceback__)
            return
        before = set(self.unlogged_dates())
        if scan["all_shifts"] != self.logger.shiftDates:
            self.logger.setShiftDates(scan["all_shifts"])
        logged = self.logger.loggedDates()
        new = (sorted(d for d in scan["all_shifts"]
                      if d >= scan["recent_start"] and d not in logged),
               scan["upcoming"], scan["shift_starts"])
        if new != (self.missedDates, self.upcomingShifts, self.shiftStarts):
            self.missedDates, self.upcomingShifts, self.shiftStarts = new
            self._uiVersion += 1
        self.show_page(self._page)
        if set(self.missedDates) - before:
            self.showNormal()
            self.showMaximized()
            self.raise_()
            self.activateWindow()

    # --- Entry point ------------------------------------------------------
    def mainloop(self):
        """Named to match the old Tk window, so main.pyw is unchanged."""
        self._qapp.exec()
