"""The home screen: title, subtitle, and the four navigation buttons to
every other screen."""
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from .. import pages


class HomeScreen(ttk.Frame):
    """Landing page. Every other screen's "← Home" button returns here."""

    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        inner = ttk.Frame(self)
        inner.grid(row=0, column=0)

        ttk.Label(inner, text="\U0001F4B0 Pay Logger", font=master.FONT_TITLE).pack(pady=(0, 4))
        ttk.Label(
            inner, text="Track your shifts, tips, and paydays",
            font=master.FONT, bootstyle="secondary"
        ).pack(pady=(0, 34))

        buttons = [
            ("＋  Add New Log", pages.NEW_LOG, "primary"),
            ("\U0001F4CB  View Logs", pages.VIEW_LOGS, "info"),
            ("\U0001F4B5  Add Payday", pages.NEW_PAYDAY, "success"),
            ("\U0001F5D1  Edit / Delete Log", pages.DELETE_LOGS, "danger-outline"),
        ]
        for label, page, style in buttons:
            ttk.Button(
                inner, text=label, bootstyle=style, width=30,
                command=lambda p=page: master.showFrame(p)
            ).pack(pady=8, ipady=12)

        ttk.Separator(inner, orient=HORIZONTAL).pack(fill=X, pady=(26, 20))
        ttk.Button(
            inner, text="Quit", bootstyle="secondary-outline", width=30,
            command=master.destroy
        ).pack(ipady=10)
