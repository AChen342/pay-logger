"""Pay Logger's GUI, as a small package instead of one big file.

Read this first if you're new to the codebase:

    gui/
        pages.py        Page-name constants used to navigate between screens.
        fonts.py         Loads the bundled Inter font (Windows-only).
        formatting.py    Turns raw spreadsheet values into display strings.
        widgets.py       Small reusable pieces: the page header bar, the
                          data-table widget, the calendar date pickers.
        charts.py        Matplotlib figure + summary numbers for the Tips
                          graph (no Tk in it).
        tips_graph.py    The Tips graph panel: controls, summary tiles,
                          and the hover highlight/tooltip.
        app.py           The App class: the window itself, page navigation,
                          and the date/money input validators every screen
                          shares.
        screens/         One module per screen (home.py = Dashboard,
                          new_log.py = Add Shift, insights.py, ...).
                          Each screen only knows about gui.pages, gui.widgets
                          and gui.formatting -- never about the other
                          screens or about App -- so any one of them can be
                          read, understood, and changed on its own.

`main.pyw` only ever needs `from gui import App`, which is re-exported here
so nothing outside this package has to know it's a package at all.
"""

from .app import App
from . import pages
from .screens.home import HomeScreen
from .screens.new_log import NewLog
from .screens.view_logs import ViewLogs
from .screens.delete_logs import DeleteLogs
from .screens.new_payday import NewPayDay
from .screens.insights import Insights

__all__ = [
    "App", "pages",
    "HomeScreen", "NewLog", "ViewLogs", "DeleteLogs", "NewPayDay", "Insights",
]
