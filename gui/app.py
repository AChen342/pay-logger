"""The application window: page navigation and the shared input validators
every screen's date/money fields use.

Building the actual page contents is left to gui.screens -- this module
only owns what's genuinely shared across all of them: the ttkbootstrap
Window itself, the Google Sheets logger handed down to every screen as
`self.logger`, and the four `validatecommand` callbacks (month/day/year/
money) that every date and money Entry in the app is wired up to.
"""
from datetime import datetime

import ttkbootstrap as ttk

import logger
from . import fonts, pages
from .screens.home import HomeScreen
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
    FONT_TITLE = fonts.TITLE
    FONT_HEAD = fonts.HEAD
    FONT_BOLD = fonts.BOLD
    FONT = fonts.BODY
    FONT_SMALL = fonts.SMALL

    def __init__(self, log=None):
        super().__init__(themename=THEME)
        self.logger = log if log is not None else logger.Logger()

        self.title("Pay Logger")
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

    def showFrame(self, page):
        """Raise the frame registered for `page` (one of the gui.pages
        constants) to the top of the window's stack."""
        self.frames[page].tkraise()

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
