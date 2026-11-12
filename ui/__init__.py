"""Pay Logger's Qt (PySide6) interface.

    ui/
        theme.py      Colors, fonts and the app-wide stylesheet (QSS).
        widgets.py    The pieces screens are built from: cards, stat tiles,
                       the sortable table, money/date inputs, the shift
                       form, the chart canvas.
        pages.py      Page-name constants used to navigate.
        app.py        The window: page stack, shared state, background
                       saving and the calendar re-check.
        screens/      One module per screen -- dashboard.py, add_shift.py,
                       view_logs.py, insights.py, edit_logs.py,
                       add_payday.py -- plus base.py (the page header and
                       the redraw-only-if-changed hook) and dialogs.py.

Everything data-related lives outside this package (`logger`, `stats`,
`goals`, `charts`, `formatting`), so the interface can be changed without
touching how the numbers are worked out -- and the old Tk interface in
`gui/` still runs off exactly the same modules.
"""

from .app import App

__all__ = ["App"]
