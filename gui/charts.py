"""Matplotlib figure + summary stats for View Logs' Tips graph, styled to
match the app's dark ("darkly") theme.

Figure is used directly (not pyplot) so no global GUI backend state is
created; ViewLogs embeds the result with FigureCanvasTkAgg.
"""
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

BG = "#222222"
FG = "#adb5bd"
GRID = "#444444"
CARD = "#3498db"
CASH = "#00bc8c"

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
    total tips, hours, shift count, average per shift, average per hour,
    and the best single day."""
    d = _daily(df, start, end)
    if d.empty:
        return None
    total_by_day = d["Card"] + d["Cash"]
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
                metric="Total tips"):
    """Stacked card + cash tip bars per day/week/month/year, limited to
    the [start, end] date range. `metric` is "Total tips" or "Tips per
    hour" (each period's tips divided by its hours).

    Pass an existing `fig` to redraw into it (it is cleared first) instead
    of making a new one -- lets the GUI keep one canvas widget alive so
    changing the view doesn't rebuild it and flash white."""
    freq, label_fmt, noun = GRANULARITIES[granularity]
    per_hour = metric == "Tips per hour"
    d = _aggregate(df, freq, start, end)

    if fig is None:
        # Auto layout re-fits the margins on every resize/redraw. (A one-off
        # tight_layout() call only fits the size at that moment, which left
        # the first draw -- made before the window had its final size --
        # with oversized margins and a smaller-looking plot.)
        fig = Figure(figsize=(8, 4.5), dpi=100, facecolor=BG,
                     constrained_layout=True)
    else:
        fig.clear()
    fig.tip_data = None  # filled in below once there are bars to hover
    ax = fig.add_subplot(111, facecolor=BG)
    title = ("Tips per Hour" if per_hour else "Tips") + " by " + noun
    ax.set_title(title, color="white", pad=12, fontsize=13, fontweight="bold")
    ax.set_ylabel("Tips per hour" if per_hour else "Tips", color=FG)
    ax.tick_params(colors=FG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))

    if d.empty:
        ax.text(0.5, 0.5, "No tips in this range", color=FG, ha="center",
                va="center", transform=ax.transAxes, fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

    labels = d["Date"].dt.strftime(label_fmt).tolist()
    hours = d["Hours"].tolist()
    card_t, cash_t = d["Card"].tolist(), d["Cash"].tolist()
    if per_hour:  # divide each period's tips by its hours (0 if none)
        card = [c / h if h > 0 else 0.0 for c, h in zip(card_t, hours)]
        cash = [c / h if h > 0 else 0.0 for c, h in zip(cash_t, hours)]
    else:
        card, cash = card_t, cash_t
    heights = [a + b for a, b in zip(card, cash)]

    tooltips = []
    for i, label in enumerate(labels):
        if per_hour:
            tooltips.append(f"{label}\nPer hour: ${heights[i]:,.2f}\n"
                            f"Total: ${card_t[i] + cash_t[i]:,.2f}\n"
                            f"Hours: {hours[i]:g}")
        else:
            tooltips.append(f"{label}\nTotal: ${heights[i]:,.2f}\n"
                            f"Card: ${card[i]:,.2f}\nCash: ${cash[i]:,.2f}\n"
                            f"Hours: {hours[i]:g}")

    x = list(range(len(labels)))
    ax.bar(x, card, color=CARD, label="Card", width=0.75)
    ax.bar(x, cash, bottom=card, color=CASH, label="Cash", width=0.75)

    # Hover tooltip: hidden until the GUI (see ViewLogs) shows it over a bar.
    ann = ax.annotate(
        "", xy=(0, 0), xytext=(0, 10), textcoords="offset points",
        ha="center", va="bottom", color="white", fontsize=9, zorder=10,
        bbox=dict(boxstyle="round,pad=0.5", fc="#303030", ec=GRID),
        annotation_clip=False)
    # Highlight box drawn over the hovered bar. Both it and the tooltip are
    # "animated" artists: the GUI blits them over a cached copy of the chart
    # on mouse-move instead of re-rendering the whole figure each time.
    hl = Rectangle((0, 0), 0.75, 0, fill=True, fc=(1, 1, 1, 0.12),
                   ec="white", lw=1.5, zorder=9)
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
        t.set_color(FG)
    return fig
