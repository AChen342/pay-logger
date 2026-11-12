"""The Dashboard (home screen): this week / month / year at a glance, goal
progress, the month-end forecast, and your latest shifts -- plus the
buttons to every other screen.

All the math lives in the top-level `stats` module; this file only lays
the numbers out.
"""
import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

import stats
from .. import pages, widgets
from ..formatting import money

PERIOD_CARDS = (("weekly", "This week"), ("monthly", "This month"),
                ("yearly", "This year"))


class HomeScreen(ttk.Frame):
    """Landing page. Every other screen's "← Home" button returns here."""

    def __init__(self, master):
        super().__init__(master)
        self.app = master
        app = master

        # --- Top bar: title + navigation ---------------------------------
        top = ttk.Frame(self)
        top.pack(fill=X, padx=32, pady=(24, 4))
        titles = ttk.Frame(top)
        titles.pack(side=LEFT)
        ttk.Label(titles, text="\U0001F4B0 Pay Logger", font=app.FONT_TITLE).pack(anchor="w")
        self.subtitle = ttk.Label(titles, text="", font=app.FONT, bootstyle="secondary")
        self.subtitle.pack(anchor="w")

        nav = ttk.Frame(top)
        nav.pack(side=RIGHT)
        buttons = [
            ("＋  Add Shift", lambda: app.showFrame(pages.NEW_LOG), "primary"),
            ("\U0001F4CB  View Logs", lambda: app.showFrame(pages.VIEW_LOGS), "info"),
            ("\U0001F4CA  Insights", lambda: app.showFrame(pages.INSIGHTS), "info"),
            ("\U0001F4B5  Add Payday", lambda: app.showFrame(pages.NEW_PAYDAY), "success"),
            ("✎  Edit / Delete", lambda: app.showFrame(pages.DELETE_LOGS), "secondary-outline"),
            ("\U0001F3AF  Goals", self.editGoals, "warning-outline"),
            ("Quit", app.destroy, "secondary-outline"),
        ]
        for label, cmd, style in buttons:
            ttk.Button(nav, text=label, bootstyle=style, command=cmd).pack(
                side=LEFT, padx=(8, 0), ipady=6)

        ttk.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=32, pady=(14, 0))

        # Reminder of shifts that still need logging.
        self.missedLabel = ttk.Label(self, text="", font=app.FONT_BOLD, bootstyle="warning")
        self.missedLabel.pack(anchor="w", padx=32, pady=(12, 0))

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=32, pady=(14, 28))
        for c in range(3):
            body.grid_columnconfigure(c, weight=1, uniform="cards")
        body.grid_rowconfigure(1, weight=1)

        # --- Row 1: this week / month / year -----------------------------
        self.periods = {}
        for col, (key, title) in enumerate(PERIOD_CARDS):
            outer, b = widgets.card(body, title, app)
            outer.grid(row=0, column=col, sticky="nsew",
                       padx=(0 if col == 0 else 8, 0 if col == 2 else 8), pady=(0, 16))
            w = {}
            w["range"] = ttk.Label(b, text="", font=app.FONT_SMALL, bootstyle="secondary")
            w["range"].pack(anchor="w")
            w["net"] = ttk.Label(b, text="—", font=app.FONT_BIG)
            w["net"].pack(anchor="w", pady=(6, 0))
            w["detail"] = ttk.Label(b, text="", font=app.FONT, bootstyle="secondary")
            w["detail"].pack(anchor="w")
            w["bar"] = ttk.Progressbar(b, maximum=100, bootstyle="success")
            w["bar"].pack(fill=X, pady=(14, 4))
            w["goal"] = ttk.Label(b, text="", font=app.FONT_SMALL)
            w["goal"].pack(anchor="w")
            w["pace"] = ttk.Label(b, text="", font=app.FONT_SMALL, bootstyle="info")
            w["pace"].pack(anchor="w", pady=(2, 0))
            self.periods[key] = w

        # --- Row 2: forecast + recent shifts -----------------------------
        outer, fb = widgets.card(body, "Month-end forecast", app)
        outer.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.fc = {}
        self.fc["projected"] = ttk.Label(fb, text="—", font=app.FONT_BIG, bootstyle="info")
        self.fc["projected"].pack(anchor="w", pady=(6, 0))
        self.fc["range"] = ttk.Label(fb, text="", font=app.FONT, bootstyle="secondary")
        self.fc["range"].pack(anchor="w")
        ttk.Separator(fb).pack(fill=X, pady=12)
        for key in ("so_far", "left", "goal"):
            self.fc[key] = ttk.Label(fb, text="", font=app.FONT, wraplength=440, justify=LEFT)
            self.fc[key].pack(anchor="w", pady=(0, 6))
        self.fc["upcoming"] = ttk.Label(fb, text="", font=app.FONT_SMALL,
                                        bootstyle="secondary", wraplength=440, justify=LEFT)
        self.fc["upcoming"].pack(anchor="w", pady=(4, 0))

        outer, rb = widgets.card(body, "Recent shifts", app)
        outer.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=(8, 0))
        self.recent = ttk.Frame(rb)
        self.recent.pack(fill=BOTH, expand=YES, pady=(8, 0))
        ttk.Button(rb, text="View all logs  →", bootstyle="link",
                   command=lambda: app.showFrame(pages.VIEW_LOGS)).pack(anchor="e")

        self._drawn = None
        self.refresh()

    # --- Refresh ----------------------------------------------------------
    def onShow(self):
        """Called by App.showFrame each time the Dashboard is shown, so it
        picks up logs added/edited on other screens."""
        self.refresh()

    def refresh(self):
        app = self.app
        if self._drawn == app.stamp():
            return  # nothing changed since the last draw
        self._drawn = app.stamp()
        today = app.today()
        self.subtitle.config(text=f"{today:%A, %B} {today.day}")
        self.refreshMissed()

        d = stats.shifts(app.logger.df)
        so_far = stats.period_totals(d, today)
        upcoming = app.upcomingShifts

        # Forecasts: week + month use the calendar (when we have it), the
        # year uses your pace.
        fcs = {}
        for key in ("weekly", "monthly", "yearly"):
            start, end = stats.PERIODS[key](today)
            fcs[key] = stats.forecast(d, today, None if key == "yearly" else upcoming,
                                      start, end)

        for key, w in self.periods.items():
            t, fc = so_far[key], fcs[key]
            start, end = stats.PERIODS[key](today)
            w["range"].config(text=f"{start:%b} {start.day} – {end:%b} {end.day}")
            w["net"].config(text=money(t["net"]))
            n = t["shifts"]
            w["detail"].config(text=(
                f"{n} shift{'s' if n != 1 else ''}  ·  {t['hours']:g} hrs  ·  "
                f"{money(t['per_hour'])}/hr") if n else "No shifts logged yet")
            goal = app.goals.get(key)
            gp = stats.goal_progress(goal, t["net"],
                                     fc["projected"] if fc else None,
                                     fc["per_shift"] if fc else None)
            if gp:
                w["bar"].configure(value=gp["pct"] * 100,
                                   bootstyle="success" if gp["pct"] >= 1 else "info")
                if gp["left"] <= 0:
                    w["goal"].config(text=f"✓ {money(goal, False)} goal reached!",
                                     bootstyle="success")
                else:
                    w["goal"].config(text=f"{gp['pct']:.0%} of {money(goal, False)} goal"
                                          f"  ·  {money(gp['left'], False)} to go",
                                     bootstyle="default")
            else:
                w["bar"].configure(value=0, bootstyle="secondary")
                w["goal"].config(text="No goal set — click \U0001F3AF Goals",
                                 bootstyle="secondary")
            w["pace"].config(text=f"On pace for ~{money(fc['projected'], False)}"
                             if fc and key != "monthly" else "")

        self._fillForecast(fcs["monthly"], app.goals.get("monthly"))
        self._fillRecent(d)

    def _fillForecast(self, fc, goal):
        f = self.fc
        if fc is None:
            f["projected"].config(text="—")
            f["range"].config(text="Log a few shifts to see a forecast")
            for k in ("so_far", "left", "goal", "upcoming"):
                f[k].config(text="")
            return
        f["projected"].config(text=money(fc["projected"], False))
        f["range"].config(text=f"Likely between {money(fc['low'], False)} and "
                               f"{money(fc['high'], False)}")
        f["so_far"].config(text=f"\U0001F4B5  {money(fc['so_far'])} earned so far this month")
        n = len(fc["remaining"])
        where = "on your schedule" if fc["source"] == "calendar" else "expected at your usual pace"
        f["left"].config(text=f"\U0001F4C5  {n} shift{'s' if n != 1 else ''} left {where}"
                              f"  ·  ~{money(fc['per_shift'], False)} per shift")
        gp = stats.goal_progress(goal, fc["so_far"], fc["projected"], fc["per_shift"])
        if gp is None:
            f["goal"].config(text="")
        elif gp["left"] <= 0:
            f["goal"].config(text=f"\U0001F3AF  Monthly goal of {money(goal, False)} reached!",
                             bootstyle="success")
        elif gp["extra_shifts"] == 0:
            f["goal"].config(text=f"\U0001F3AF  On track for your {money(goal, False)} goal",
                             bootstyle="success")
        else:
            k = gp["extra_shifts"]
            f["goal"].config(text=f"\U0001F3AF  Pick up ~{k} more shift{'s' if k != 1 else ''}"
                                  f" to hit your {money(goal, False)} goal",
                             bootstyle="warning")
        if fc["source"] == "calendar" and fc["remaining"]:
            days = ", ".join(f"{u:%a} {u.month}/{u.day}" for u in fc["remaining"][:10])
            more = len(fc["remaining"]) - 10
            f["upcoming"].config(text="Upcoming: " + days + (f" +{more} more" if more > 0 else ""))
        elif fc["source"] == "pace":
            f["upcoming"].config(text="Open the app with dashboard.pyw to use your "
                                      "calendar schedule for this.")
        else:
            f["upcoming"].config(text="")

    def _fillRecent(self, d):
        for child in self.recent.winfo_children():
            child.destroy()
        app = self.app
        rows = d.tail(10).iloc[::-1]
        if rows.empty:
            ttk.Label(self.recent, text="No shifts logged yet.", font=app.FONT,
                      bootstyle="secondary").grid(row=0, column=0, sticky="w")
            return
        self.recent.grid_columnconfigure(4, weight=1)
        for i, (_, r) in enumerate(rows.iterrows()):
            pad = (0, 10)
            ttk.Label(self.recent, text=f"{r['Date']:%a %m/%d}", font=app.FONT_BOLD).grid(
                row=i, column=0, sticky="w", padx=(0, 18), pady=pad)
            ttk.Label(self.recent, text=r["Type"] or "—", font=app.FONT,
                      bootstyle="secondary", width=8).grid(row=i, column=1, sticky="w", pady=pad)
            ttk.Label(self.recent, text=money(r["Net"]), font=app.FONT_BOLD,
                      bootstyle="success", width=10, anchor=E).grid(row=i, column=2, sticky="e", pady=pad)
            per = money(r["Net"] / r["Hours"]) + "/hr" if r["Hours"] > 0 else ""
            ttk.Label(self.recent, text=per, font=app.FONT, bootstyle="secondary",
                      width=11, anchor=E).grid(row=i, column=3, sticky="e", padx=(0, 18), pady=pad)
            note = r["Notes"]
            if r["Section"]:
                note = f"Section {r['Section']}" + (f"  ·  {note}" if note else "")
            if len(note) > 60:
                note = note[:57] + "…"
            ttk.Label(self.recent, text=note, font=app.FONT_SMALL,
                      bootstyle="secondary").grid(row=i, column=4, sticky="w", pady=pad)

    def refreshMissed(self):
        """Update the reminder listing shifts that still have no tip log."""
        pending = self.app.unloggedDates()
        if pending:
            days = ", ".join(f"{d:%a %m/%d}" for d in pending)
            noun = "shift" if len(pending) == 1 else "shifts"
            self.missedLabel.config(text=f"⚠  Unlogged {noun}: {days}", bootstyle="warning")
            self.missedLabel.pack(anchor="w", padx=32, pady=(12, 0))
        else:
            self.missedLabel.config(text="")
            self.missedLabel.pack_forget()

    # --- Goals ---------------------------------------------------------
    def editGoals(self):
        GoalsDialog(self.app)


class GoalsDialog(tk.Toplevel):
    """Set weekly / monthly / yearly take-home tip goals (blank = none)."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Income Goals")
        self.transient(app)
        self.resizable(False, False)

        form = ttk.Frame(self, padding=24)
        form.pack()
        ttk.Label(form, text="Take-home tip goals", font=app.FONT_HEAD).grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(form, text="Leave a box blank for no goal.", font=app.FONT_SMALL,
                  bootstyle="secondary").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.entries = {}
        for i, (key, label) in enumerate((("weekly", "Weekly"), ("monthly", "Monthly"),
                                          ("yearly", "Yearly")), start=2):
            ttk.Label(form, text=label, font=app.FONT_BOLD).grid(
                row=i, column=0, sticky="w", pady=8, padx=(0, 18))
            e = ttk.Entry(form, width=14, validate="key", validatecommand=app.moneyCmd)
            e.grid(row=i, column=1, sticky="w", pady=8)
            if app.goals.get(key):
                e.insert(0, f"{app.goals[key]:g}")
            self.entries[key] = e

        btns = ttk.Frame(form)
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Button(btns, text="Save", bootstyle="primary", width=12,
                   command=self._save).pack(side=LEFT, padx=(0, 10), ipady=4)
        ttk.Button(btns, text="Cancel", bootstyle="secondary-outline", width=12,
                   command=self.destroy).pack(side=LEFT, ipady=4)

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.entries["weekly"].focus_set()

    def _save(self):
        out = {}
        for key, e in self.entries.items():
            try:
                v = float(e.get())
                out[key] = v if v > 0 else None
            except ValueError:
                out[key] = None
        self.app.setGoals(out)
        self.destroy()
