"""View Logs: five tabs (Tips / Weekly / Monthly / Yearly / Payday) over
one searchable table, and a Graph View for the Tips tab."""
from PySide6.QtWidgets import QStackedWidget

import formatting
from .. import widgets
from ..widgets import DataTable, row
from .base import Screen
from .tips_graph import TipsGraph

TABS = (("Tips", "tips"), ("Weekly", "weekly"), ("Monthly", "monthly"),
        ("Yearly", "yearly"), ("Payday", "payday"))

# Weekly/Monthly/Yearly: (column holding the period, display format).
PERIOD_TABS = {"weekly": ("Week Ending", "%m/%d/%Y"),
               "monthly": ("Month", "%m/%Y"),
               "yearly": ("Year", "%Y")}

PAYDAY_HEADERS = ["Start", "End", "Hours", "Gross", "Tax", "Work Pay",
                  "Card", "Cash", "Tips", "Before Tax", "After Tax", "Hourly"]


class ViewLogs(Screen):
    """"View Logs" screen."""

    title = "View Logs"

    def __init__(self, app):
        super().__init__(app)
        self._kind = "tips"
        self._graph_mode = False

        self.tabs = {}
        for text, kind in TABS:
            self.tabs[kind] = widgets.button(
                text, "tab", lambda _=False, k=kind: self.show_tab(k))
        self.mode_button = widgets.button("Graph View", None, self.toggle_mode)
        self.body.addWidget(row(*self.tabs.values(), None, self.mode_button,
                                spacing=2))

        # Table and graph share one slot; only one is ever visible.
        self.stack = QStackedWidget()
        self.table = DataTable(formatting.TIP_HEADERS, searchable=True)
        self.graph = TipsGraph(app)
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.graph)
        self.body.addWidget(self.stack, 1)

        self.show_tab("tips")

    # --- Tabs -----------------------------------------------------------
    def stamp(self):
        return (self._kind, self._graph_mode, self.app.stamp())

    def show_tab(self, kind):
        """Switch tabs. Graph View exists only for Tips."""
        self._kind = kind
        for k, b in self.tabs.items():
            b.setProperty("active", "true" if k == kind else "false")
            widgets.restyle(b)
        self.mode_button.setVisible(kind == "tips")
        if kind != "tips" and self._graph_mode:
            self._set_graph_mode(False)
        self.refresh_now()

    def toggle_mode(self):
        self._set_graph_mode(not self._graph_mode)
        self.refresh_now()

    def _set_graph_mode(self, on):
        self._graph_mode = on
        self.stack.setCurrentWidget(self.graph if on else self.table)
        self.mode_button.setText("Table View" if on else "Graph View")

    def warm_up(self):
        """Build the chart once at startup so the first toggle is instant."""
        self.graph.refresh()

    # --- Drawing --------------------------------------------------------
    def refresh(self):
        if self._graph_mode:
            self.graph.refresh()
            return
        lg = self.app.logger
        kind = self._kind
        if kind == "tips":
            headers, rows = formatting.TIP_HEADERS, formatting.tip_rows(lg.df[::-1])
        elif kind == "payday":
            headers, rows = PAYDAY_HEADERS, formatting.payday_rows(lg.dfPayDay[::-1])
        else:
            col, fmt = PERIOD_TABS[kind]
            df = {"weekly": lg.dfWeekly, "monthly": lg.dfMonthly,
                  "yearly": lg.dfYearly}[kind]
            headers = [col, "Hours", "Card", "Cash", "Take-home"]
            rows = formatting.period_rows(df[::-1], col, fmt)
        # The Tips tab has a long Notes column, so it sizes to content;
        # the others are all numbers and share the width evenly.
        self.table.set_fit("contents" if kind == "tips" else "stretch")
        self.table.load(headers, rows)
