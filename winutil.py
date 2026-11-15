"""Small Windows helpers shared by the launcher's modules."""
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]


def _fits_bin(path):
    """Windows permanently deletes anything over a drive's Recycle Bin limit, so check first, with a 10%
    margin. A limit that can't be read counts as no room."""
    try:
        import winreg
        buf = ctypes.create_unicode_buffer(64)
        if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(path.resolve().anchor, buf, 64):
            return False
        base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket"

        def dword(sub, name, default=None):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as key:
                    return winreg.QueryValueEx(key, name)[0]
            except OSError:
                return default

        vol = base + "\\Volume\\" + buf.value[buf.value.index("{"):buf.value.index("}") + 1]
        limit_mb = dword(vol, "MaxCapacity")
        if limit_mb is None or dword(vol, "NukeOnDelete", 0) == 1 or dword(base, "NukeOnDelete", 0) == 1:
            return False
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else path.stat().st_size
        return size <= limit_mb * 1024 ** 2 * 0.9
    except (OSError, ValueError):
        return False


def recycle(path):
    """Sends a file or folder to the Recycle Bin (never deletes outright). Returns True on success;
    on False the file is left where it is."""
    path = Path(path)
    if not path.exists():
        return True
    if sys.platform != "win32" or not _fits_bin(path):
        return False
    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    op = _SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom=str(path.resolve()) + "\0",
                          fFlags=FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI)
    ok = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not op.fAnyOperationsAborted
    return ok and not path.exists()


# Which screen games use, as in EchoForge (app/screens.js). With three screens the middle one is the game screen, at
# 1920 x 1080: either Windows reports three (or more) monitors, or one very wide screen made of several (NVIDIA
# Surround / AMD Eyefinity spanning, which Windows reports as a single display, e.g. 5846 x 1080 for three monitors
# and their bezels). On one ordinary screen games keep going fullscreen as before.
WIDE = 4.4  # width / height of a spanned screen: three 16:9 monitors are 5.33, two are 3.56 (not treated as three)


def game_screen(monitors):
    """monitors: [(x, y, width, height)]. Returns (multi, (x, y, width, height) of the game screen or None)."""
    mons = [m for m in monitors if m[2] > 0 and m[3] > 0]
    if not mons:
        return False, None
    if len(mons) >= 3:
        by_x = sorted(mons, key=lambda m: (m[0], m[1]))
        return True, tuple(by_x[(len(by_x) - 1) // 2])
    x, y, w, h = max(mons, key=lambda m: m[2] * m[3])  # the main (largest) screen
    if w / h >= WIDE:
        gw = min(w, round(h * 16 / 9))  # 1080 high -> 1920 wide
        return True, (x + round((w - gw) / 2), y, gw, h)
    return False, (x, y, w, h)


def monitors():
    """Each monitor's (x, y, width, height), in real pixels."""
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    try:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2: real pixels, not scaled ones
    except (AttributeError, OSError):
        pass
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def add(_mon, _dc, rect, _data):
        r = rect.contents
        found.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True
    user32.EnumDisplayMonitors(None, None, proc(add), 0)
    return found


def retroarch_game_screen_cfg(rect):
    """RetroArch settings that put its window on the game screen, borderless, with no menu bar, given with
    --appendconfig so retroarch.cfg is never changed. Saving settings when RetroArch closes is off for that session,
    or these would be written into retroarch.cfg; core options, save states and remaps are saved separately and still are."""
    x, y, w, h = rect
    return "\n".join([
        'config_save_on_exit = "false"', 'video_fullscreen = "false"', 'video_windowed_fullscreen = "false"',
        'video_window_save_positions = "true"', 'video_window_show_decorations = "false"', 'ui_menubar_enable = "false"',
        f'video_windowed_position_x = "{x}"', f'video_windowed_position_y = "{y}"',
        f'video_windowed_position_width = "{w}"', f'video_windowed_position_height = "{h}"']) + "\n"
