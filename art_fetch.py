"""Matches games to thumbnails.libretro.com (the art library RetroArch uses).

Box art, in-game screenshots and title screens are saved where RetroArch looks
for them (thumbnails/<playlist>/Named_*), so RetroArch's own menus show them too.
"""
import difflib
import html
import re
import urllib.parse
import urllib.request

BASE = "https://thumbnails.libretro.com/"
HEADERS = {"User-Agent": "JLDigitalRetroGaming/1.0"}
KINDS = ("Named_Boxarts", "Named_Snaps", "Named_Titles")
REGION_ORDER = ["USA", "World", "Europe", "Japan"]
REGION_WORDS = {"USA": "USA", "US": "USA", "JP-US": "USA", "U": "USA", "World": "World",
                "Europe": "Europe", "EU": "Europe", "E": "Europe", "Japan": "Japan", "JP": "Japan", "J": "Japan"}


def fetch(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout).read()


def norm(title):
    """Comparable form of a title: no tags, 'The' moved to the front, letters and digits only."""
    t = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", title)
    t = re.sub(r"\s+Rev\s+\w+", "", t).strip()
    m = re.match(r"^(.*?), (The|A|An)( - .*)?$", t)
    if m:
        t = f"{m.group(2)} {m.group(1)}{m.group(3) or ''}"
    t = t.replace("&", "")  # the thumbnail server writes "&" as "_", which is dropped below
    return re.sub(r"[^a-z0-9]", "", t.lower())


def regions(name):
    found = []
    for tag in re.findall(r"\(([^)]*)\)", name):
        for word in re.split(r"[,\s]+", tag):
            if word in REGION_WORDS:
                found.append(REGION_WORDS[word])
    return found


def rank(name, want_region):
    """Lower is better: clean No-Intro names in the right region first."""
    score = 0
    if "[" in name:
        score += 50  # bad dumps, hacks, pirates
    if re.search(r"\(\d{4}", name):
        score += 30  # TOSEC-style names
    if re.search(r"\((Beta|Proto|Demo|Sample|Unl|Pirate|Hack)", name, re.I):
        score += 20
    reg = regions(name)
    order = ([want_region] if want_region else []) + REGION_ORDER
    score += min((order.index(r) for r in reg if r in order), default=len(order)) * 3
    score += name.count("(")
    return score


def server_system(playlist):
    return "MAME" if playlist.startswith("MAME") else playlist


def index_for(system, kind="Named_Boxarts", cache={}):
    key = (system, kind)
    if key not in cache:
        url = BASE + urllib.parse.quote(f"{system}/{kind}/")
        page = fetch(url, timeout=120).decode("utf-8", "replace")
        names = [html.unescape(urllib.parse.unquote(h)) for h in re.findall(r'href="([^"]+\.png)"', page)]
        by_norm = {}
        for n in names:
            by_norm.setdefault(norm(n[:-4]), []).append(n)
        cache[key] = by_norm
    return cache[key]


def best_match(game, by_norm):
    key = norm(game["label"])
    candidates = by_norm.get(key)
    if not candidates:
        close = difflib.get_close_matches(key, by_norm.keys(), n=1, cutoff=0.9)
        candidates = by_norm[close[0]] if close else None
    if not candidates:
        return None
    want = {"USA": "USA", "EUR": "Europe", "JPN": "Japan", "WORLD": "World", "JP/US": "USA"}.get(game["region"])
    return min(candidates, key=lambda n: rank(n, want))


def download(game, kind, dest):
    """Saves the best match for a game to dest. Returns the server's file name, or None."""
    system = server_system(game["playlist"])
    name = best_match(game, index_for(system, kind))
    if not name:
        return None
    data = fetch(BASE + urllib.parse.quote(f"{system}/{kind}/{name}"))
    if not data.startswith(b"\x89PNG"):
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return name
