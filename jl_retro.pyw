"""EchoForge Retro Gaming - a launcher for RetroArch.

Runs a small server on 127.0.0.1 that reads RetroArch's playlists and
launches games, then opens the dashboard in an Edge app window. Shuts itself
down shortly after the dashboard window is closed.

In the background it also fetches missing box art, screenshots and title
screens, picks up playlist changes, watches a folder you choose for game files and
backs up saves after each session.
"""
import hashlib
import io
import json
import os
import re
import shutil
import string
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art_fetch  # noqa: E402
import rom_inbox  # noqa: E402
import save_backup  # noqa: E402
import synopsis  # noqa: E402
import padquit  # noqa: E402
import selfupdate  # noqa: E402

APP_NAME = "EchoForge Retro Gaming"
APP_VERSION = "2.4.0"
APP_DIR = Path(__file__).resolve().parent
# Installed, an update replaces the program files, so data lives in the user's profile.
# Run from source, everything stays next to the script as it always has.
INSTALLED = (APP_DIR / "installed.txt").exists()
WEB_DIR = APP_DIR / "web"
DATA_DIR = Path(os.environ.get("EF_RETRO_DATA") or (Path(os.environ["LOCALAPPDATA"]) / APP_NAME if INSTALLED else APP_DIR))
CACHE_DIR = DATA_DIR / "cache"
STATE_FILE = DATA_DIR / "state.json"
RA_DIR = Path(r"D:\RetroArch-Win64")  # replaced at startup by find_retroarch()
RA_EXE = RA_DIR / "retroarch.exe"
RA_SETUP_NAME = "RetroArch-Win64-setup.exe"
RA_SETUP_URL = "https://buildbot.libretro.com/stable/1.22.2/windows/x86_64/" + RA_SETUP_NAME
CORE_URL = "https://buildbot.libretro.com/nightly/windows/x86_64/latest/{}.zip"
HOST, PORT = "127.0.0.1", int(os.environ.get("EF_RETRO_PORT") or 8765)
ORIGIN = f"http://{HOST}:{PORT}"
EDGE_PATHS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]
IDLE_SHUTDOWN_SECONDS = 90
ART_RETRY_SECONDS = 7 * 86400
THUMB_WIDTH = 360

# Playlist name -> (system id, default core). Arcade playlists each keep the
# MAME core version their ROM set was built for.
PLAYLISTS = {
    "Nintendo - Nintendo Entertainment System": ("nes", "fceumm_libretro.dll"),
    "Nintendo - Super Nintendo Entertainment System": ("snes", "bsnes2014_performance_libretro.dll"),
    "Nintendo - Nintendo 64": ("n64", "parallel_n64_libretro.dll"),
    "Nintendo - Game Boy": ("gb", "gambatte_libretro.dll"),
    "Nintendo - Game Boy Color": ("gbc", "gambatte_libretro.dll"),
    "Sega - Mega Drive - Genesis": ("genesis", "genesis_plus_gx_libretro.dll"),
    "Sega - Game Gear": ("gamegear", "genesis_plus_gx_libretro.dll"),
    "Sega - 32X": ("32x", "picodrive_libretro.dll"),
    "Sony - PlayStation": ("psx", "pcsx_rearmed_libretro.dll"),
    "Nintendo - Wii": ("wii", "dolphin_libretro.dll"),
    "Nintendo - GameCube": ("gamecube", "dolphin_libretro.dll"),
    "Sega - Dreamcast": ("dreamcast", "flycast_libretro.dll"),
    "MAME 2000": ("arcade", "mame2000_libretro.dll"),
    "MAME 2003-Plus": ("arcade", "mame2003_plus_libretro.dll"),
    "MAME 2010": ("arcade", "mame2010_libretro.dll"),
    "MAME 2015": ("arcade", "mame2015_libretro.dll"),
    "MAME 2016": ("arcade", "mame2016_libretro.dll"),
}
PLAYLIST_FOR = {}
for _name, (_sys, _core) in PLAYLISTS.items():
    PLAYLIST_FOR.setdefault(_sys, _name)
# Arcade ROMs that crash on their playlist's MAME core, mapped to the core
# each one was tested working on (October 2026).
CORE_OVERRIDES = {
    "outrun.zip": "mame_libretro.dll",
    "1941.zip": "mame_libretro.dll",
    "ga2.zip": "mame_libretro.dll",
    "bublbob2.zip": "mame_libretro.dll",
    "kof2002.zip": "mame_libretro.dll",
    "ghouls.zip": "mame2003_plus_libretro.dll",
    "nbajam.zip": "mame2003_plus_libretro.dll",
    "suzuka8h.zip": "mame2003_plus_libretro.dll",
    "aburner2.zip": "mame2003_plus_libretro.dll",
    "wwfmania.zip": "mame2003_plus_libretro.dll",
    "spidmanu.zip": "mame_libretro.dll",
    "abcop.zip": "mame_libretro.dll",
    "alieninv.zip": "mame_libretro.dll",
    "alieninvp2.zip": "mame_libretro.dll",
    "alinvade.zip": "mame_libretro.dll",
    "aburner.zip": "mame2003_plus_libretro.dll",
}
# ROMs that crashed on every installed core; hidden from the dashboard.
UNPLAYABLE = {"aoh.zip"}
SYSTEMS = [
    {"id": "nes", "name": "NES", "full": "Nintendo Entertainment System"},
    {"id": "snes", "name": "Super Nintendo", "full": "Super Nintendo Entertainment System"},
    {"id": "n64", "name": "Nintendo 64", "full": "Nintendo 64"},
    {"id": "arcade", "name": "Arcade", "full": "Arcade (MAME)"},
    {"id": "gb", "name": "Game Boy", "full": "Nintendo Game Boy"},
    {"id": "gbc", "name": "Game Boy Color", "full": "Nintendo Game Boy Color"},
    {"id": "genesis", "name": "Genesis", "full": "Sega Genesis"},
    {"id": "gamegear", "name": "Game Gear", "full": "Sega Game Gear"},
    {"id": "32x", "name": "Sega 32X", "full": "Sega 32X"},
    {"id": "psx", "name": "PlayStation", "full": "Sony PlayStation"},
    {"id": "wii", "name": "Wii", "full": "Nintendo Wii"},
    {"id": "gamecube", "name": "GameCube", "full": "Nintendo GameCube"},
    {"id": "dreamcast", "name": "Dreamcast", "full": "Sega Dreamcast"},
]
REGIONS = {"USA": "USA", "Europe": "EUR", "Japan": "JPN", "Asia": "ASIA",
           "World": "WORLD", "JP-US": "JP/US", "Australia": "AUS"}
DEFAULT_SETTINGS = {"fullscreen": True, "backupAfterPlay": True, "backupWeekly": True, "backupLast": 0,
                    "backupRoot": str(DATA_DIR / "Backups" if INSTALLED else save_backup.DEFAULT_ROOT),
                    "inboxFolder": "", "fetchArt": True, "retroarchDir": "",
                    "synopses": True, "padQuit": True, "padMenu": True, "autoUpdate": True, "updateChecked": 0,
                    "skin": "retro", "skins": [], "scanlines": True,
                    "homeLayout": "classic", "layouts": [], "home": None, "pinned": []}
ABOUT_RETRY_SECONDS = 30 * 86400
ABOUT_FILE_NAME = "synopses.json"
about_lock = threading.Lock()
update_info = {"last": None, "busy": False, "pct": 0, "error": ""}

state_lock = threading.Lock()
core_lock = threading.Lock()
# RetroArch download progress for the setup screen: "", "downloading" or "installing".
ra_setup = {"phase": "", "pct": 0, "error": ""}
game_proc = {"proc": None, "game": None}
last_ping = [time.time()]
# version goes up whenever the library or its art changes, so the page knows to reload.
lib_info = {"version": 1, "stamp": None, "art_busy": False, "backup_busy": False}


def clean_title(label):
    tags = re.findall(r"[\(\[]([^\)\]]*)[\)\]]", label)
    title = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", label)
    title = re.sub(r"\s+Rev\s+\w+", "", title).strip()
    m = re.match(r"^(.*?), (The|A|An)( - .*)?$", title)
    if m:
        title = f"{m.group(2)} {m.group(1)}{m.group(3) or ''}"
    title = title.replace(" - ", ": ", 1)
    region = ""
    for tag in tags:
        word = tag.split()[0] if tag.split() else ""
        if word in REGIONS:
            region = REGIONS[word]
            break
    return title, region


def thumb_path(playlist, label, kind="Named_Boxarts"):
    """Where RetroArch keeps a playlist entry's art of one kind (its own naming rule)."""
    safe = re.sub(r'[&*/:`<>?\\|"]', "_", label)
    return RA_DIR / "thumbnails" / playlist / kind / f"{safe}.png"


def art_path(playlist, label):
    return thumb_path(playlist, label, "Named_Boxarts")


def playlist_stamp():
    return tuple((p.name, p.stat().st_mtime_ns) for p in sorted((RA_DIR / "playlists").glob("*.lpl")))


def load_games():
    games, seen_paths, seen_titles = [], set(), set()
    for lpl in sorted((RA_DIR / "playlists").glob("*.lpl")):
        if lpl.stem not in PLAYLISTS:
            continue
        system, default_core = PLAYLISTS[lpl.stem]
        try:
            items = json.loads(lpl.read_text(encoding="utf-8")).get("items", [])
        except (OSError, ValueError):
            continue
        for item in items:
            path = item.get("path", "")
            if not path or path in seen_paths:
                continue
            title, region = clean_title(item.get("label") or Path(path).stem)
            key = (system, title.lower(), region)
            if key in seen_titles:
                continue
            rom_file = Path(path.split("#")[0]).name.lower()
            if rom_file in UNPLAYABLE:
                continue
            core = item.get("core_path", "")
            if rom_file in CORE_OVERRIDES:
                core = str(RA_DIR / "cores" / CORE_OVERRIDES[rom_file])
            elif core in ("", "DETECT") or not Path(core).exists():
                core = str(RA_DIR / "cores" / default_core)
            seen_paths.add(path)
            seen_titles.add(key)
            label = item.get("label") or Path(path).stem
            games.append({
                "id": hashlib.sha1(path.encode("utf-8")).hexdigest()[:12],
                "title": title,
                "region": region,
                "system": system,
                "path": path,
                "core": core,
                "label": label,
                "playlist": lpl.stem,
                "art": art_path(lpl.stem, label),
                "snap": thumb_path(lpl.stem, label, "Named_Snaps"),
                "titleShot": thumb_path(lpl.stem, label, "Named_Titles"),
            })
    games.sort(key=lambda g: g["title"].lower())
    return games


def read_state():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("favorites", [])
    data.setdefault("history", {})
    data.setdefault("settings", {})
    for k, v in DEFAULT_SETTINGS.items():
        data["settings"].setdefault(k, v)
    return data


def write_state(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def update_settings(**changes):
    with state_lock:
        data = read_state()
        data["settings"].update(changes)
        write_state(data)
        return data["settings"]


ID = re.compile(r"[\w-]{1,40}")
SETTING_BOOLS = ("fullscreen", "backupAfterPlay", "backupWeekly", "fetchArt", "synopses", "padQuit", "padMenu",
                 "autoUpdate", "scanlines")


def small_dict(d, limit=1500):
    """Plain data only (skins and layouts): short, JSON-safe, no nesting deeper than a list of words."""
    if not isinstance(d, dict) or len(json.dumps(d)) > limit:
        return None
    ok = lambda v: isinstance(v, (str, int, float, bool)) or v is None or (  # noqa: E731
        isinstance(v, list) and len(v) <= 20 and all(isinstance(x, (str, int, float, bool)) for x in v))
    return {str(k)[:30]: v for k, v in d.items() if ok(v)}


def clean_settings(body):
    """The settings the dashboard may change, each checked. The page checks skins again before using them."""
    changes = {k: bool(body[k]) for k in SETTING_BOOLS if k in body}
    for k in ("skin", "homeLayout"):
        if isinstance(body.get(k), str) and ID.fullmatch(body[k]):
            changes[k] = body[k]
    for k, most in (("skins", 30), ("layouts", 20)):
        if isinstance(body.get(k), list):
            changes[k] = [c for c in (small_dict(x) for x in body[k][:most]) if c]
    if "home" in body:
        changes["home"] = small_dict(body["home"]) if body["home"] else None
    if isinstance(body.get("pinned"), list):
        changes["pinned"] = [x for x in body["pinned"][:60] if isinstance(x, str) and re.fullmatch(r"[0-9a-f]{12}", x)]
    return changes


def running_game():
    proc = game_proc["proc"]
    if proc and proc.poll() is None:
        return game_proc["game"]
    return None


def bring_to_front(pid, timeout=15):
    """Windows keeps new windows from a background process behind the dashboard,
    where RetroArch pauses itself. Wait for the game window and bring it forward."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []
    proc_cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def check(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    deadline = time.time() + timeout
    while time.time() < deadline and not found:
        time.sleep(0.3)
        user32.EnumWindows(proc_cb(check), 0)
    if found:
        time.sleep(0.5)
        user32.keybd_event(0x12, 0, 0, 0)  # tapping Alt lets this process change the foreground window
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(found[0])


def ensure_core(core):
    """A fresh RetroArch has no cores: fetch the one this game needs from RetroArch's official
    buildbot. Returns an error message, or "" when the core is ready."""
    path = Path(core)
    with core_lock:
        if path.exists():
            return ""
        if not re.fullmatch(r"[a-z0-9_]+_libretro\.dll", path.name):
            return f"The emulator core {path.name} is missing."
        tmp = path.with_name(path.name + ".part")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(CORE_URL.format(path.name), headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(req, timeout=120) as r:
                pack = zipfile.ZipFile(io.BytesIO(r.read()))
            if pack.testzip() is not None:
                return f"The download of {path.name} was damaged. Try again."
            tmp.write_bytes(pack.read(path.name))
            tmp.replace(path)
            return ""
        except (OSError, KeyError, zipfile.BadZipFile) as e:
            tmp.unlink(missing_ok=True)
            return f"Couldn't download the emulator core {path.name}: {e}"


def launch(game, fullscreen):
    if running_game():
        return False, "A game is already running."
    if not RA_EXE.exists():
        return False, f"RetroArch was not found at {RA_EXE}."
    err = ensure_core(game["core"])
    if err:
        return False, err
    args =[str(RA_EXE)] + (["-f"] if fullscreen else []) + ["-L", game["core"], game["path"]]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = game_proc["proc"] = subprocess.Popen(args, cwd=str(RA_DIR), creationflags=flags)
    game_proc["game"] = game
    threading.Thread(target=bring_to_front, args=(proc.pid,), daemon=True).start()
    watch_pad(proc)
    with state_lock:
        data = read_state()
        entry = data["history"].get(game["id"], {"plays": 0})
        entry["plays"] += 1
        entry["last"] = int(time.time())
        data["history"][game["id"]] = entry
        write_state(data)
    return True, ""


def watch_pad(proc):
    """Select + Start while the game runs: a tap opens RetroArch's Quick Menu, holding it for 2 seconds quits."""
    settings = read_state()["settings"]
    if sys.platform != "win32" or not (settings.get("padQuit", True) or settings.get("padMenu", True)) or not padquit.SCRIPT.exists():
        return
    quitting = []

    def on_quit():
        if settings.get("padQuit", True) and not quitting:
            quitting.append(1)
            threading.Thread(target=padquit.close_gently, args=(proc.pid,), kwargs={"wait": lambda: proc.poll() is not None},
                             daemon=True).start()

    try:
        w = padquit.Watcher(proc.pid, on_quit=on_quit)
    except OSError:
        return
    if settings.get("padMenu", True):
        w.on_menu = w.open_menu

    def end_with_game():
        proc.wait()
        w.stop()
    threading.Thread(target=end_with_game, daemon=True).start()


# ---- Synopses (Wikipedia), kept in the cache so they also work offline ----

def about_store():
    try:
        return json.loads((CACHE_DIR / ABOUT_FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def about_save(store):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / (ABOUT_FILE_NAME + ".tmp")
    tmp.write_text(json.dumps(store), encoding="utf-8")
    tmp.replace(CACHE_DIR / ABOUT_FILE_NAME)


def system_full(system_id):
    return next((s["full"] for s in SYSTEMS if s["id"] == system_id), "")


def fetch_about(game, force=False):
    """Looks a game up on Wikipedia unless it's known, a recent miss, or marked as the wrong game. Returns the entry."""
    with about_lock:
        entry = about_store().get(game["id"])
    if entry and not force and ("text" in entry or entry.get("wrong") or time.time() - entry.get("tried", 0) < ABOUT_RETRY_SECONDS):
        return entry
    stem = Path(game["path"].split("#")[0]).stem
    r = synopsis.lookup([game["title"], clean_title(stem)[0]], system_full(game["system"]))
    new = {k: r[k] for k in ("text", "title", "url", "year", "genre", "dev", "pub") if k in r} if r.get("ok") else {}
    new["tried"] = int(time.time())
    with about_lock:
        store = about_store()
        store[game["id"]] = new
        about_save(store)
    return new


def about_worker():
    """Looks up every game in the background, one at a time. Misses are retried after 30 days."""
    if not read_state()["settings"].get("synopses", True):
        return
    for g in list(Handler.games):
        with about_lock:
            entry = about_store().get(g["id"])
        if entry and ("text" in entry or entry.get("wrong") or time.time() - entry.get("tried", 0) < ABOUT_RETRY_SECONDS):
            continue
        if not read_state()["settings"].get("synopses", True):
            return
        try:
            fetch_about(g)
        except (OSError, ValueError):
            return  # offline or Wikipedia is down: try again next start
        time.sleep(0.3)


# ---- Updates from GitHub ----

def check_update():
    update_info["last"] = selfupdate.check(APP_VERSION)
    update_settings(updateChecked=int(time.time()))
    return update_info["last"]


def install_update():
    """Downloads the newer installer, checks it, starts it and closes this app so it can replace the program files."""
    last = update_info["last"]
    if not last or not last.get("update"):
        last = check_update()
    if not last.get("ok"):
        update_info.update(busy=False, error=last.get("error", ""))
        return
    try:
        path = selfupdate.download(last["latest"], DATA_DIR / "downloads", lambda pct: update_info.update(pct=pct))
        os.startfile(path)  # the installer closes this app itself and asks before replacing anything
        update_info.update(busy=False, pct=100)
    except (OSError, ValueError) as e:
        update_info.update(busy=False, pct=0, error=str(e))


# ---- Small covers for the grid: full box art is often 500 KB+ per game ----

def small_cover(game):
    """JPEG bytes of the box art scaled to THUMB_WIDTH, cached on disk. None if Pillow is missing."""
    try:
        from PIL import Image
    except ImportError:
        return None
    src = game["art"]
    out = CACHE_DIR / "covers" / f"{game['id']}-{src.stat().st_mtime_ns}.jpg"
    if out.exists():
        return out.read_bytes()
    with Image.open(src) as im:
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (23, 12, 54))
        bg.paste(im, mask=im.split()[3])
        if bg.width > THUMB_WIDTH:
            bg = bg.resize((THUMB_WIDTH, round(bg.height * THUMB_WIDTH / bg.width)), Image.LANCZOS)
        buf = io.BytesIO()
        bg.save(buf, "JPEG", quality=86, optimize=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    for old in out.parent.glob(f"{game['id']}-*.jpg"):
        old.unlink(missing_ok=True)
    out.write_bytes(buf.getvalue())
    return buf.getvalue()


# ---- Finding RetroArch and moving in from the old location ----

def is_retroarch(folder):
    try:
        return (Path(folder) / "retroarch.exe").is_file()
    except OSError:  # a damaged or unreadable drive
        return False


def playlist_items(folder):
    """How many games a RetroArch copy lists, to tell a real library from a spare copy."""
    total = 0
    for lpl in (Path(folder) / "playlists").glob("*.lpl"):
        if lpl.stem in PLAYLISTS:
            try:
                total += len(json.loads(lpl.read_text(encoding="utf-8")).get("items", []))
            except (OSError, ValueError):
                pass
    return total


def find_retroarch():
    """The folder the user chose, otherwise the copy with the most games among the usual install places
    on every drive. A PC can hold more than one copy, so the first one found isn't good enough."""
    env = os.environ
    chosen = read_state()["settings"].get("retroarchDir")
    if chosen and is_retroarch(chosen):
        return Path(chosen)
    if env.get("EF_RETRO_RA"):
        return Path(env["EF_RETRO_RA"]) if is_retroarch(env["EF_RETRO_RA"]) else None
    places = [Path(env.get("LOCALAPPDATA", "")) / "Programs" / "RetroArch", Path(env.get("APPDATA", "")) / "RetroArch",
              Path(env.get("PROGRAMFILES", "")) / "RetroArch"]
    places += [f"{d}:\\{name}" for d in string.ascii_uppercase for name in ("RetroArch-Win64", "RetroArch")]
    found = [Path(p) for p in places if is_retroarch(p)]
    return max(found, key=playlist_items) if found else None


def use_retroarch(folder, starting=False, chosen=False):
    global RA_DIR, RA_EXE
    RA_DIR, RA_EXE = Path(folder), Path(folder) / "retroarch.exe"
    if chosen:  # only the user's own choice is remembered, so a better copy can still be found later
        update_settings(retroarchDir=str(RA_DIR))
    ra_setup.update(phase="", pct=0, error="")
    try:
        (DATA_DIR / "downloads" / RA_SETUP_NAME).unlink(missing_ok=True)
    except OSError:
        pass  # its installer is still open; removed next start
    if not starting:
        reload_library()
        threading.Thread(target=art_worker, daemon=True).start()


def download_retroarch():
    """Fetches RetroArch's official installer and opens it. Its own window takes it from there;
    the watchdog notices when retroarch.exe appears."""
    dest = DATA_DIR / "downloads" / RA_SETUP_NAME
    part = dest.with_name(dest.name + ".part")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(RA_SETUP_URL, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(req, timeout=60) as r, part.open("wb") as out:
            total, got = int(r.headers.get("Content-Length") or 0), 0
            while chunk := r.read(1024 * 1024):
                out.write(chunk)
                got += len(chunk)
                ra_setup["pct"] = round(got * 100 / total) if total else 0
        if not got or (total and got != total):
            raise OSError("the download came out the wrong size")
        part.replace(dest)
        ra_setup.update(phase="installing", pct=100)
        os.startfile(dest)  # may ask for administrator approval, which subprocess can't do
    except OSError as e:
        part.unlink(missing_ok=True)
        ra_setup.update(phase="", pct=0, error=f"Couldn't get RetroArch: {e}")


# ---- Background jobs ----

def reload_library():
    Handler.games = load_games()
    Handler.by_id = {g["id"]: g for g in Handler.games}
    lib_info["stamp"] = playlist_stamp()
    lib_info["version"] += 1


def art_worker():
    """Fetches missing box art, screenshots and title screens. Misses are retried after a week."""
    if not read_state()["settings"].get("fetchArt", True):
        return
    misses_file = CACHE_DIR / "art-misses.json"
    try:
        misses = json.loads(misses_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        misses = {}
    now = time.time()
    dead_systems = set()
    lib_info["art_busy"] = True
    changed_at = 0
    try:
        for kind, field in (("Named_Boxarts", "art"), ("Named_Snaps", "snap"), ("Named_Titles", "titleShot")):
            for g in list(Handler.games):
                key = f"{kind}|{g['playlist']}|{g['label']}"
                system = art_fetch.server_system(g["playlist"])
                if g[field].exists() or now - misses.get(key, 0) < ART_RETRY_SECONDS or (system, kind) in dead_systems:
                    continue
                try:
                    if art_fetch.download(g, kind, g[field]):
                        if time.time() - changed_at > 4:
                            lib_info["version"] += 1
                            changed_at = time.time()
                    else:
                        misses[key] = now
                except OSError:
                    dead_systems.add((system, kind))  # offline or the server is down: try again next start
                time.sleep(0.15)
            CACHE_DIR.mkdir(exist_ok=True)
            misses_file.write_text(json.dumps(misses), encoding="utf-8")
    finally:
        lib_info["art_busy"] = False
        lib_info["version"] += 1


def run_backup(reason):
    if not RA_EXE.exists():
        return {"ok": False, "error": "RetroArch wasn't found."}
    if lib_info["backup_busy"]:
        return {"ok": False, "error": "A backup is already running."}
    lib_info["backup_busy"] = True
    try:
        settings = read_state()["settings"]
        result = save_backup.run(RA_DIR, settings["backupRoot"], reason)
        if result["ok"]:
            update_settings(backupLast=int(time.time()))
        return result
    finally:
        lib_info["backup_busy"] = False


def inbox_folder():
    folder = read_state()["settings"].get("inboxFolder")
    return Path(folder) if folder else None


class Handler(BaseHTTPRequestHandler):
    games = []
    by_id = {}

    def log_message(self, *args):
        pass

    def host_ok(self):
        return self.headers.get("Host") in (f"{HOST}:{PORT}", f"localhost:{PORT}")

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body, ctype, cache="max-age=86400"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.host_ok():
            return self.send_error(403)
        last_ping[0] = time.time()
        route = self.path.split("?")[0]
        if route == "/api/setup":
            return self.send_json({"ready": RA_EXE.exists(), "version": APP_VERSION, **ra_setup,
                                   "saved": read_state()["settings"].get("retroarchDir", "")})
        if route == "/api/library":
            data = read_state()
            public = [dict({k: g[k] for k in ("id", "title", "region", "system")},
                           art=g["art"].exists(), snap=g["snap"].exists(), titleShot=g["titleShot"].exists())
                      for g in self.games]
            return self.send_json({"systems": SYSTEMS, "games": public, "favorites": data["favorites"],
                                   "history": data["history"], "settings": data["settings"],
                                   "series": data.get("series", {}), "version": lib_info["version"]})
        if route == "/api/status":
            game = running_game()
            return self.send_json({"running": game["id"] if game else None, "version": lib_info["version"],
                                   "artBusy": lib_info["art_busy"], "backupBusy": lib_info["backup_busy"]})
        if route == "/api/inbox":
            folder = inbox_folder()
            items = rom_inbox.scan(folder, set(PLAYLIST_FOR)) if folder else []
            return self.send_json({"folder": str(folder) if folder else "", "items": items})
        if route == "/api/backups":
            settings = read_state()["settings"]
            return self.send_json({"root": settings["backupRoot"], "last": settings["backupLast"],
                                   "busy": lib_info["backup_busy"],
                                   "snapshots": save_backup.snapshots(settings["backupRoot"]),
                                   "sources": [{"label": l, "path": str(p)} for l, p in save_backup.sources(RA_DIR)]})
        for prefix, field in (("/art/", "art"), ("/thumb/", "art"), ("/snap/", "snap"), ("/title/", "titleShot")):
            if route.startswith(prefix):
                game = self.by_id.get(route[len(prefix):])
                if not game or not game[field].exists():
                    return self.send_error(404)
                if prefix == "/thumb/":
                    try:
                        small = small_cover(game)
                    except OSError:
                        small = None
                    if small:
                        return self.send_bytes(small, "image/jpeg", "max-age=604800")
                return self.send_bytes(game[field].read_bytes(), "image/png", "max-age=604800")
        if route.startswith("/api/about/"):
            game = self.by_id.get(route[len("/api/about/"):])
            if not game:
                return self.send_json({"ok": False}, 404)
            own = read_state().get("about", {}).get(game["id"], {})
            entry = {}
            if read_state()["settings"].get("synopses", True) and not own.get("wrong"):
                try:
                    entry = fetch_about(game)
                except (OSError, ValueError):
                    with about_lock:
                        entry = about_store().get(game["id"], {})
            return self.send_json({"ok": True, "own": own.get("text", ""), "wrong": bool(own.get("wrong")),
                                   **({} if own.get("wrong") else {k: v for k, v in entry.items() if k != "tried"})})
        if route == "/api/update":
            return self.send_json({"current": APP_VERSION, "installed": INSTALLED, "last": update_info["last"],
                                   "busy": update_info["busy"], "pct": update_info["pct"], "error": update_info["error"]})
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/skins.js": ("skins.js", "text/javascript; charset=utf-8"),
                 "/custom.js": ("custom.js", "text/javascript; charset=utf-8"),
                 "/icon.png": ("icon.png", "image/png"),
                 "/logo.svg": ("logo.svg", "image/svg+xml"),
                 "/PressStart2P.ttf": ("PressStart2P.ttf", "font/ttf")}
        if route in files:
            name, ctype = files[route]
            return self.send_bytes((WEB_DIR / name).read_bytes(), ctype, "no-cache")
        self.send_error(404)

    def do_POST(self):
        # Only the dashboard itself may trigger actions.
        if not self.host_ok() or self.headers.get("Origin") != ORIGIN:
            return self.send_error(403)
        length = min(int(self.headers.get("Content-Length") or 0), 100000)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            body = {}
        route = self.path.split("?")[0]
        by_id = self.by_id
        if route == "/api/setup/download":
            if not RA_EXE.exists() and ra_setup["phase"] != "downloading":
                ra_setup.update(phase="downloading", pct=0, error="")
                threading.Thread(target=download_retroarch, daemon=True).start()
            return self.send_json({"ok": True})
        if route == "/api/setup/folder":
            folder = str(body.get("path", "")).strip().strip('"')
            if folder.lower().endswith("retroarch.exe"):
                folder = str(Path(folder).parent)
            if not folder or not is_retroarch(folder):
                return self.send_json({"ok": False, "error": "There's no retroarch.exe in that folder."})
            use_retroarch(folder, chosen=True)
            return self.send_json({"ok": True})
        if route == "/api/launch":
            game = by_id.get(body.get("id"))
            if not game:
                return self.send_json({"ok": False, "error": "Unknown game."}, 404)
            ok, err = launch(game, read_state()["settings"].get("fullscreen", True))
            return self.send_json({"ok": ok, "error": err}, 200 if ok else 409)
        if route == "/api/favorite":
            gid = body.get("id")
            if gid not in by_id:
                return self.send_json({"ok": False}, 404)
            with state_lock:
                data = read_state()
                favs = data["favorites"]
                if body.get("on"):
                    if gid not in favs:
                        favs.append(gid)
                elif gid in favs:
                    favs.remove(gid)
                write_state(data)
            return self.send_json({"ok": True, "favorites": favs})
        if route == "/api/series":
            # A game's collection: a name moves it there, "-" keeps it out, "" goes back to automatic.
            gid, name = body.get("id"), str(body.get("name", "")).strip()[:60]
            if gid not in by_id:
                return self.send_json({"ok": False}, 404)
            with state_lock:
                data = read_state()
                series = data.setdefault("series", {})
                if name:
                    series[gid] = name
                else:
                    series.pop(gid, None)
                write_state(data)
            return self.send_json({"ok": True, "series": series})
        if route == "/api/settings":
            changes = clean_settings(body)
            settings = update_settings(**changes)
            if changes.get("synopses"):
                threading.Thread(target=about_worker, daemon=True).start()
            return self.send_json({"ok": True, "settings": settings})
        if route == "/api/about":
            # Your own text for a game ("" goes back to Wikipedia's), "wrong" for a mismatch, or "lookup" to ask again.
            game = by_id.get(body.get("id"))
            if not game:
                return self.send_json({"ok": False}, 404)
            with state_lock:
                data = read_state()
                about = data.setdefault("about", {})
                mine = about.get(game["id"], {})
                if "text" in body:
                    text = str(body["text"]).strip()[:4000]
                    mine = {**mine, "text": text} if text else {k: v for k, v in mine.items() if k != "text"}
                if body.get("wrong"):
                    mine["wrong"] = True
                if body.get("lookup"):
                    mine.pop("wrong", None)
                if mine:
                    about[game["id"]] = mine
                else:
                    about.pop(game["id"], None)
                write_state(data)
            if body.get("wrong"):
                with about_lock:
                    store = about_store()
                    store[game["id"]] = {"wrong": True, "tried": int(time.time())}
                    about_save(store)
            entry = {}
            if body.get("lookup"):
                try:
                    entry = fetch_about(game, force=True)
                except (OSError, ValueError) as e:
                    return self.send_json({"ok": False, "error": f"Couldn't reach Wikipedia ({e})."})
            return self.send_json({"ok": True, "found": "text" in entry})
        if route == "/api/update/check":
            return self.send_json(check_update())
        if route == "/api/update/install":
            if running_game():
                return self.send_json({"ok": False, "error": "Quit your game first."})
            if not INSTALLED:
                return self.send_json({"ok": False, "error": "This copy runs from its source folder. Update it with git, or install it."})
            if not update_info["busy"]:
                update_info.update(busy=True, pct=0, error="")
                threading.Thread(target=install_update, daemon=True).start()
            return self.send_json({"ok": True})
        if route == "/api/inbox/folder":
            folder = str(body.get("path", "")).strip().strip('"')
            if not folder or not Path(folder).is_dir():
                return self.send_json({"ok": False, "error": "That folder doesn't exist."})
            update_settings(inboxFolder=folder)
            return self.send_json({"ok": True})
        if route == "/api/inbox/add":
            if not RA_EXE.exists():
                return self.send_json({"ok": False, "added": [], "errors": [{"error": "RetroArch wasn't found."}]})
            folder = inbox_folder()
            if not folder:
                return self.send_json({"ok": False, "added": [], "errors": [{"error": "Choose a folder first."}]})
            folder = folder.resolve()
            items = rom_inbox.scan(folder, set(PLAYLIST_FOR))
            wanted = [i for i in items if i["status"] == "ready" and (body.get("all") or i["file"] == body.get("file"))]
            added, errors = [], []
            for item in wanted:
                if Path(item["file"]).resolve().parent != folder:
                    continue
                r = rom_inbox.add(item["file"], RA_DIR, PLAYLIST_FOR)
                (added if r["ok"] else errors).append(dict(r, name=item["name"]))
            if added:
                reload_library()
                threading.Thread(target=art_worker, daemon=True).start()
            return self.send_json({"ok": not errors, "added": added, "errors": errors})
        if route == "/api/backup/run":
            return self.send_json(run_backup("manual"))
        if route == "/api/backup/restore":
            if running_game():
                return self.send_json({"ok": False, "error": "Quit the game first, so its saves aren't in use."})
            if not RA_EXE.exists():
                return self.send_json({"ok": False, "error": "RetroArch wasn't found."})
            settings = read_state()["settings"]
            return self.send_json(save_backup.restore(RA_DIR, settings["backupRoot"], str(body.get("name", ""))))
        if route == "/api/bye":
            # Window closed: shut down soon unless it reconnects (a reload).
            last_ping[0] = time.time() - IDLE_SHUTDOWN_SECONDS + 5
            return self.send_json({"ok": True})
        self.send_error(404)


def open_window():
    url = ORIGIN + "/"
    for edge in EDGE_PATHS:
        if edge.exists():
            subprocess.Popen([str(edge), f"--app={url}", "--start-maximized"])
            return
    webbrowser.open(url)


def already_running():
    try:
        with urllib.request.urlopen(ORIGIN + "/api/status", timeout=1) as r:
            return r.status == 200
    except OSError:
        return False


def watchdog(server):
    was_running = False
    while True:
        time.sleep(3)
        playing = running_game() is not None
        if was_running and not playing and read_state()["settings"].get("backupAfterPlay", True):
            threading.Thread(target=run_backup, args=("after play",), daemon=True).start()
        was_running = playing
        if not RA_EXE.exists():
            found = find_retroarch()
            if found:
                use_retroarch(found)
        try:
            if playlist_stamp() != lib_info["stamp"]:
                reload_library()
        except OSError:
            pass
        if not playing and time.time() - last_ping[0] > IDLE_SHUTDOWN_SECONDS:
            server.shutdown()
            return


def startup_jobs():
    settings = read_state()["settings"]
    if INSTALLED and settings.get("autoUpdate", True) and time.time() - settings.get("updateChecked", 0) > 86400:
        check_update()  # once a day; nothing installs until Update now is pressed
    if settings.get("backupWeekly", True) and time.time() - settings.get("backupLast", 0) > save_backup.WEEK:
        run_backup("weekly")
    for g in list(Handler.games):  # make the grid's small covers ahead of time
        try:
            if g["art"].exists():
                small_cover(g)
        except OSError:
            pass
    art_worker()
    about_worker()


def main():
    if already_running():
        if "--no-window" not in sys.argv:
            open_window()
        return
    found = find_retroarch()
    if found:
        use_retroarch(found, starting=True)
    else:
        globals().update(RA_DIR=DATA_DIR / "no-retroarch", RA_EXE=DATA_DIR / "no-retroarch" / "retroarch.exe")
    reload_library()
    server =ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Thread(target=watchdog, args=(server,), daemon=True).start()
    threading.Thread(target=startup_jobs, daemon=True).start()
    if "--no-window" not in sys.argv:
        open_window()
    server.serve_forever()


if __name__ == "__main__":
    main()
