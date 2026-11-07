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
