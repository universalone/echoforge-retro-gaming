"""Add games: finds game files in the folder you choose and adds them.

A ROM's system is told from the cartridge file inside (loose, .zip or .7z), never
from the file's name. Each import copies the file to roms\\<system>, checks
its size, adds it to that system's RetroArch playlist and sends the original to
the Recycle Bin. Programs and shortcuts are never run or touched. Disc games
(PlayStation, GameCube, Wii) are left for EchoForge's own import folder.
"""
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

from winutil import recycle

SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
ROM_EXT = {".nes": "nes", ".fds": "nes", ".sfc": "snes", ".smc": "snes", ".z64": "n64", ".n64": "n64", ".v64": "n64",
           ".gb": "gb", ".gbc": "gbc", ".md": "genesis", ".gen": "genesis", ".smd": "genesis", ".gg": "gamegear",
           ".32x": "32x"}
IGNORED_INSIDE = {".txt", ".nfo", ".diz", ".url", ".jpg", ".png", ".htm", ".html"}
PARTIAL_EXT = {".crdownload", ".part", ".tmp", ".download", ".partial", ".opdownload"}
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _entries(path):
    """[(inner name, size, crc)] of a .zip or .7z, or None if it can't be read."""
    ext = path.suffix.lower()
    try:
        if ext == ".zip":
            with zipfile.ZipFile(path) as z:
                return [(i.filename, i.file_size, f"{i.CRC:08X}") for i in z.infolist() if not i.is_dir()]
        if ext == ".7z" and SEVEN_ZIP.exists():
            out = subprocess.run([str(SEVEN_ZIP), "l", "-slt", "-ba", str(path)], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
            if out.returncode != 0:
                return None
            items = []
            for block in out.stdout.split("\n\n"):
                info = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
                if info.get("Path") and "D" not in info.get("Attributes", ""):
                    items.append((info["Path"], int(info.get("Size") or 0), (info.get("CRC") or "").upper()))
            return items
    except (OSError, zipfile.BadZipFile, ValueError, subprocess.SubprocessError):
        return None
    return None


_memo = {}


def classify(path):
    """{"system", "rom", "crc"} for a game file, or None if it isn't one. Remembered per file version,
    so the page's regular refresh doesn't reopen every archive."""
    try:
        st = path.stat()
    except OSError:
        return None
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _memo:
        _memo[key] = _classify(path)
    return _memo[key]


def _classify(path):
    ext = path.suffix.lower()
    if ext in ROM_EXT:
        return {"system": ROM_EXT[ext], "rom": None, "crc": None}
    if ext not in (".zip", ".7z"):
        return None
    entries = _entries(path)
    if not entries:
        return None
    roms = [e for e in entries if Path(e[0]).suffix.lower() in ROM_EXT]
    others = [e for e in entries if Path(e[0]).suffix.lower() not in set(ROM_EXT) | IGNORED_INSIDE]
    if len(roms) != 1 or others:
        return None  # arcade sets, multi-game packs and anything with programs inside are left alone
    name, _, crc = roms[0]
    return {"system": ROM_EXT[Path(name).suffix.lower()], "rom": name, "crc": crc}


def scan(folder, systems):
    folder = Path(folder)
    items = []
    if not folder.is_dir():
        return items
    names = {p.name.lower() for p in folder.iterdir()}
    for p in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if not p.is_file() or p.suffix.lower() in PARTIAL_EXT:
            continue
        info = classify(p)
        if not info or info["system"] not in systems:
            continue
        st = p.stat()
        busy = any((p.name + e).lower() in names for e in PARTIAL_EXT) or time.time() - st.st_mtime < 8
        label = Path(info["rom"] or p.name).stem
        items.append({"file": str(p), "name": p.name, "size": st.st_size, "system": info["system"],
                      "label": label, "status": "copying" if busy else "ready"})
    return items


def _crc_of(path):
    crc = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def add(file, ra_dir, playlist_for):
    """Imports one file. playlist_for maps a system id to its playlist name.
    Returns {"ok", "system", "label", "error"?}."""
    src = Path(file)
    info = classify(src) if src.is_file() else None
    if not info:
        return {"ok": False, "error": "That file isn't a game anymore."}
    system = info["system"]
    dest = Path(ra_dir) / "roms" / system / src.name
    playlist = Path(ra_dir) / "playlists" / f"{playlist_for[system]}.lpl"
    entry_path = f"{dest}#{info['rom']}" if info["rom"] else str(dest)
    label = Path(info["rom"] or src.name).stem
    try:
        data = json.loads(playlist.read_text(encoding="utf-8")) if playlist.exists() else {
            "version": "1.5", "default_core_path": "", "default_core_name": "", "label_display_mode": 0,
            "right_thumbnail_mode": 0, "left_thumbnail_mode": 0, "thumbnail_match_mode": 0, "sort_mode": 0,
            "items": []}
        already = any(i.get("path") == entry_path for i in data["items"])
        if not (dest.exists() and dest.stat().st_size == src.stat().st_size):
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            shutil.copy2(src, tmp)
            if tmp.stat().st_size != src.stat().st_size:
                tmp.unlink()
                return {"ok": False, "error": "The copy came out the wrong size, so the original was kept."}
            tmp.replace(dest)
        if not already:
            data["items"].append({"path": entry_path, "label": label, "core_path": "DETECT", "core_name": "DETECT",
                                  "crc32": f"{info['crc'] or _crc_of(dest)}|crc", "db_name": playlist.name})
            tmp = playlist.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(playlist)
    except (OSError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    recycle(src)
    return {"ok": True, "system": system, "label": label, "already": already}
