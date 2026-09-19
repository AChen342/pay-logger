"""One module per screen (home, new_log, view_logs, delete_logs,
new_payday). Each screen only imports gui.pages, gui.widgets and
gui.formatting -- never another screen, and never gui.app -- so any one of
them can be read and changed on its own, and gui/app.py is free to import
all of them without any risk of a circular import.
"""
