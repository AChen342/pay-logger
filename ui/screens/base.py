"""What every screen shares: the page header, the body layout, and the
"only redraw when something changed" hook.
"""
from PySide6.QtWidgets import (QFrame, QScrollArea, QVBoxLayout, QWidget)

from .. import pages, widgets


class Screen(QWidget):
    """Base page. Subclasses set `title` and build into `self.body`.

    `on_show()` is called every time the page is raised; it calls
    `refresh()` only when `App.stamp()` differs from the last draw, which
    is what keeps switching pages instant.
    """

    title = ""
    back_button = True
    # Screens made of cards (rather than one big table) set this: when the
    # window is too short the page scrolls instead of squeezing the cards
    # until their text overlaps.
    scrollable = False

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._drawn = None

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 18, 36, 18)
        root.setSpacing(12)
        if self.title:
            back = widgets.button("←  Home", "ghost",
                                  lambda: app.show_page(pages.HOME))
            root.addWidget(widgets.row(
                widgets.label(self.title, role="title"), None,
                *( [back] if self.back_button else [] )))

        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        if self.scrollable:
            inner = QWidget()
            inner.setLayout(self.body)
            area = QScrollArea()
            area.setWidget(inner)
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.viewport().setAutoFillBackground(False)
            inner.setAutoFillBackground(False)
            root.addWidget(area, 1)
        else:
            root.addLayout(self.body, 1)

    # --- Redraw control ---------------------------------------------
    def on_show(self):
        if self._drawn != self.stamp():
            self._drawn = self.stamp()
            self.refresh()

    def stamp(self):
        """What "unchanged" means for this screen. Screens with their own
        controls (a range picker, a tab) fold those in."""
        return self.app.stamp()

    def invalidate(self):
        """Force the next on_show() (or refresh_now()) to redraw."""
        self._drawn = None

    def refresh_now(self):
        self._drawn = self.stamp()
        self.refresh()

    def refresh(self):
        """Fill the screen from current data. Overridden by subclasses."""
