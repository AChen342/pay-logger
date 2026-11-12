"""Moved to the top-level `charts` module, so both GUIs can use it.

This shim keeps the old Tk GUI (gui/tips_graph.py) working unchanged.
"""
from charts import *  # noqa: F401,F403
