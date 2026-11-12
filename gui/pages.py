"""Page-name constants used to navigate between screens.

Screens navigate to each other (e.g. NewLog's "Back" button returns to
HomeScreen) but must not import each other directly: each screen lives in
its own module, and importing sibling screens would tangle them together in
a circular import (HomeScreen needs to know about NewLog/ViewLogs/etc. to
build its nav buttons; every other screen needs to know about HomeScreen for
its own "back" button).

Instead, every screen and app.py agree on a plain string name for each
page. This module has no dependencies of its own, so any screen can import
it without pulling in the rest of the GUI.
"""

HOME = "home"
NEW_LOG = "new_log"
VIEW_LOGS = "view_logs"
DELETE_LOGS = "delete_logs"
NEW_PAYDAY = "new_payday"
INSIGHTS = "insights"
