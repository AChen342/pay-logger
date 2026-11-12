"""Opens Pay Logger as a normal window (main.pyw starts minimized when
nothing needs logging). If it's already running, brings that window to the
front instead."""
import os
import runpy
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.argv = [os.path.join(APP_DIR, "main.pyw"), "--open"]
runpy.run_path(sys.argv[0], run_name="__main__")
