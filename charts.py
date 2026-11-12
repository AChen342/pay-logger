"""Matplotlib figure + summary stats for View Logs' Tips graph, styled to
match the app's dark ("darkly") theme.

Figure is used directly (not pyplot) so no global GUI backend state is
created; ViewLogs embeds the result with FigureCanvasTkAgg.
"""
from typing import NamedTuple

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

class Palette(NamedTuple):
    """The colors one figure is drawn in. Two interfaces share this module
    (the Qt one is light, the old Tk one dark), so colors are passed in
    rather than baked in."""
    bg: str        # figure + axes background
    fg: str        # axis labels and ticks
    grid: str      # gridlines and spines
    card: str      # card tips
    cash: str      # cash tips
    tipout: str    # tip-out (drawn below zero)
    text: str      # titles and bar labels
    hi: str        # the bar worth pointing at (best weekday)


DARK = Palette(bg="#222222", fg="#adb5bd", grid="#444444", card="#3498db",
               cash="#00bc8c", tipout="#e74c3c", text="white", hi="#00bc8c")

LIGHT = Palette(bg="#ffffff", fg="#74787e", grid="#ebebe6", card="#5587bb",
                cash="#58a98c", tipout="#c47f72", text="#23262a", hi="#3f9d7f")

# The Qt dark theme: quieter than DARK, and drawn on the card color rather
# than on the page, so the chart sits inside its card without a seam.
NIGHT = Palette(bg="#1e2125", fg="#8b9298", grid="#2e3338", card="#5b8ab8",
                cash="#4fa98a", tipout="#c0786c", text="#eceef0", hi="#3ec291")

# The names the old Tk GUI reads off this module.
BG, FG, GRID = DARK.bg, DARK.fg, DARK.grid
CARD, CASH, TIPOUT = DARK.card, DARK.cash, DARK.tipout

# granularity -> (pandas freq, x-label format, name used in the title)
GRANULARITIES = {
    "Day":   (None, "%m/%d/%y", "Day"),
    "Week":  ("W", "%m/%d/%y", "Week (week ending)"),
    "Month": ("MS", "%b %Y", "Month"),
    "Year":  ("YS", "%Y", "Year"),
}

METRICS = ("Total tips", "Tips per hour")


def _num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _daily(df, start=None, end=None):
    """Daily-sheet rows within [start, end] (either may be None = open),
    as a clean (Date, Hours, Card, Cash) frame."""
    d = pd.DataFrame({
        "Date": pd.to_datetime(df["Date"], errors="coerce"),
        "Hours": _num(df["Hours"]),
        "Card": _num(df["Card"]),
        "Cash": _num(df["Cash"]),
        "TipOut": _num(df["Tip Out"]) if "Tip Out" in df.columns else 0.0,
    }).dropna(subset=["Date"])
    if start is not None:
        d = d[d["Date"] >= pd.Timestamp(start)]
    if end is not None:
        d = d[d["Date"] <= pd.Timestamp(end)]
    return d


def _aggregate(df, freq, start=None, end=None):
    """One (Date, Hours, Card, Cash) row per period, oldest first. Periods
    with no shift logged are left out."""
    d = _daily(df, start, end)
    if freq is not None:
        d = d.groupby(pd.Grouper(key="Date", freq=freq)).sum().reset_index()
        d = d[((d["Card"] + d["Cash"]) > 0) | (d["Hours"] > 0)]
    return d.sort_values("Date")


def summary(df, start=None, end=None):
    """Headline numbers for the range, or None if it has no shifts:
    total take-home tips (card + cash - tip out), hours, shift count, average per shift, average per hour,
    and the best single day."""
    d = _daily(df, start, end)
    if d.empty:
        return None
    total_by_day = d["Card"] + d["Cash"] - d["TipOut"]
    total, hours = float(total_by_day.sum()), float(d["Hours"].sum())
    best = total_by_day.idxmax()
    return {
        "total": total,
        "hours": hours,
        "shifts": len(d),
        "avg_shift": total / len(d),
        "avg_hour": total / hours if hours > 0 else 0.0,
        "best_date": d.loc[best, "Date"],
        "best_amount": float(total_by_day.loc[best]),
    }


def tips_figure(df, granularity="Day", start=None, end=None, fig=None,
                metric="Total tips", palette=DARK):
    """Stacked card + cash tip bars per day/week/month/year, limited to
    the [start, end] date range. `metric` is "Total tips" or "Tips per
    hour" (each period's tips divided by its hours).

    Pass an existing `fig` to redraw into it (it is cleared first) instead
    of making a new one -- lets the GUI keep one canvas widget alive so
    changing the view doesn't rebuild it and flash white."""
    p = palette
    freq, label_fmt, noun = GRANULARITIES[granularity]
    per_hour = metric == "Tips per hour"
    d = _aggregate(df, freq, start, end)

    if fig is None:
        # Auto layout re-fits the margins on every resize/redraw. (A one-off
        # tight_layout() call only fits the size at that moment, which left
        # the first draw -- made before the window had its final size --
        # with oversized margins and a smaller-looking plot.)
        fig = Figure(figsize=(8, 4.5), dpi=100, facecolor=p.bg,
                     constrained_layout=True)
    else:
        fig.clear()
    fig.tip_data = None  # filled in below once there are bars to hover
    ax = fig.add_subplot(111, facecolor=p.bg)
    title = ("Tips per Hour" if per_hour else "Tips") + " by " + noun
    ax.set_title(title, color=p.text, pad=12, fontsize=13, fontweight="bold")
    ax.set_ylabel("Tips per hour" if per_hour else "Tips", color=p.fg)
    ax.tick_params(colors=p.fg)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(p.grid)
    ax.grid(axis="y", color=p.grid, linewidth=0.9)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))

    if d.empty:
        ax.text(0.5, 0.5, "No tips in this range", color=p.fg, ha="center",
                va="center", transform=ax.transAxes, fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

    labels = d["Date"].dt.strftime(label_fmt).tolist()
    hours = d["Hours"].tolist()
    card_t, cash_t, out_t = d["Card"].tolist(), d["Cash"].tolist(), d["TipOut"].tolist()
    if per_hour:  # divide each period's tips by its hours (0 if none)
        div = lambda vals: [v / h if h > 0 else 0.0 for v, h in zip(vals, hours)]
        card, cash, out = div(card_t), div(cash_t), div(out_t)
    else:
        card, cash, out = card_t, cash_t, out_t
    heights = [a + b for a, b in zip(card, cash)]

    tooltips = []
    for i, label in enumerate(labels):
        net = card_t[i] + cash_t[i] - out_t[i]
        lines = [label]
        if per_hour:
            lines.append(f"Take-home/hr: ${heights[i] - out[i]:,.2f}")
        lines.append(f"Card: ${card_t[i]:,.2f}   Cash: ${cash_t[i]:,.2f}")
        if out_t[i]:
            lines.append(f"Tip out: -${out_t[i]:,.2f}")
        lines.append(f"Take-home: ${net:,.2f}")
        lines.append(f"Hours: {hours[i]:g}")
        tooltips.append("\n".join(lines))

    x = list(range(len(labels)))
    ax.bar(x, card, color=p.card, label="Card", width=0.75)
    ax.bar(x, cash, bottom=card, color=p.cash, label="Cash", width=0.75)
    if any(out):  # tip-outs hang below zero
        ax.bar(x, [-v for v in out], color=p.tipout, label="Tip out", width=0.75)
        ax.axhline(0, color=p.grid, linewidth=0.8)

    # Hover tooltip: hidden until the GUI (see ViewLogs) shows it over a bar.
    ann = ax.annotate(
        "", xy=(0, 0), xytext=(0, 10), textcoords="offset points",
        ha="center", va="bottom", color=p.text, fontsize=9, zorder=10,
        bbox=dict(boxstyle="round,pad=0.5", fc=p.bg, ec=p.grid),
        annotation_clip=False)
    # Highlight box drawn over the hovered bar. Both it and the tooltip are
    # "animated" artists: the GUI blits them over a cached copy of the chart
    # on mouse-move instead of re-rendering the whole figure each time.
    hl = Rectangle((0, 0), 0.75, 0, fill=True, fc=(0, 0, 0, 0.06),
                   ec=p.text, lw=1.5, zorder=9)
    ax.add_patch(hl)
    for art in (ann, hl):
        art.set_visible(False)
        art.set_animated(True)
        art.set_in_layout(False)  # must never shift the plot layout
    fig.tip_data = {"ax": ax, "ann": ann, "hl": hl, "width": 0.75,
                    "tooltips": tooltips, "heights": heights}

    # Sparse tick labels so long histories stay readable.
    step = max(1, len(labels) // 12)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right")
    leg = ax.legend(frameon=False, loc="upper left")
    for t in leg.get_texts():
        t.set_color(p.fg)
    return fig


def weekday_figure(table, fig=None, palette=DARK):
    """Average take-home per shift by weekday (Mon..Sun), from a
    stats.breakdown(d, "Weekday") table. Same redraw-in-place contract as
    tips_figure."""
    p = palette
    if fig is None:
        fig = Figure(figsize=(6, 3.2), dpi=100, facecolor=p.bg, constrained_layout=True)
    else:
        fig.clear()
        fig.set_facecolor(p.bg)
    ax = fig.add_subplot(111, facecolor=p.bg)
    ax.tick_params(colors=p.fg, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(p.grid)
    ax.grid(axis="y", color=p.grid, linewidth=0.9)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))

    days = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday")
    vals = dict(zip(table["Group"], table["Avg shift"])) if len(table) else {}
    counts = dict(zip(table["Group"], table["Shifts"])) if len(table) else {}
    if not vals:
        ax.text(0.5, 0.5, "No shifts in this range", color=p.fg, ha="center",
                va="center", transform=ax.transAxes, fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])
        return fig
    heights = [vals.get(d, 0) for d in days]
    best = max(heights)
    colors = [p.hi if h == best and h > 0 else p.card for h in heights]
    bars = ax.bar(range(7), heights, color=colors, width=0.62)
    for b, d in zip(bars, days):
        if counts.get(d):
            ax.annotate(f"${vals[d]:,.0f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                        xytext=(0, 5), textcoords="offset points", ha="center",
                        color=p.text, fontsize=9)
    ax.set_xticks(range(7))
    ax.set_xticklabels([d[:3] for d in days])
    ax.set_ylim(0, best * 1.2 if best > 0 else 1)
    return fig
