"""Loads the bundled Inter font.

Ships Inter (a clean, modern UI typeface: https://rsms.me/inter/) next to
the app and registers it with Windows for this process only (the
FR_PRIVATE flag), so it renders correctly on any machine without installing
anything system-wide or needing admin rights. Falls back to Segoe UI if the
font files are missing or this isn't Windows.

Nothing here needs Tk or ttkbootstrap -- app.py just reads the FONT_*
tuples this module computes at import time and hands them to widgets as
`font=`.
"""
import atexit
import os
import sys

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_PACKAGE_DIR)
_FONT_DIR = os.path.join(_APP_DIR, "fonts")
_FONT_FILES = ("Inter-Regular.ttf", "Inter-Bold.ttf")
_FR_PRIVATE = 0x10

_loaded_fonts = []


def _gdi32():
    """Return a gdi32 handle with the two functions we need configured, or
    None off Windows or if ctypes/gdi32 aren't available."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        dll = ctypes.WinDLL("gdi32")
        dll.AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
        dll.AddFontResourceExW.restype = ctypes.c_int
        dll.RemoveFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
        return dll
    except Exception:
        return None


def _load_bundled_fonts():
    """Register the bundled Inter .ttf files with Windows for this process
    only. Returns True iff at least one font file was registered."""
    gdi32 = _gdi32()
    if gdi32 is None:
        return False
    try:
        for name in _FONT_FILES:
            path = os.path.join(_FONT_DIR, name)
            if os.path.exists(path) and gdi32.AddFontResourceExW(path, _FR_PRIVATE, None):
                _loaded_fonts.append(path)
    except Exception:
        return False
    return len(_loaded_fonts) > 0


def _unload_bundled_fonts():
    """Undo _load_bundled_fonts(). Registered with atexit so the process
    always cleans up its private font registrations on the way out."""
    if not _loaded_fonts:
        return
    gdi32 = _gdi32()
    if gdi32 is None:
        return
    try:
        for path in _loaded_fonts:
            gdi32.RemoveFontResourceExW(path, _FR_PRIVATE, None)
    except Exception:
        pass


INTER_AVAILABLE = _load_bundled_fonts()
atexit.register(_unload_bundled_fonts)

FAMILY = "Inter" if INTER_AVAILABLE else "Segoe UI"
TITLE = (FAMILY, 22, "bold")
HEAD = (FAMILY, 13, "bold")
BOLD = (FAMILY, 11, "bold")
BODY = (FAMILY, 11)
SMALL = (FAMILY, 9)
