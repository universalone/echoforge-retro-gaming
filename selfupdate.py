"""EchoForge Retro Gaming's own updates: checks the project's GitHub Releases for a newer installer, downloads it,
checks it against the SHA-256 GitHub publishes, then starts it. Nothing installs until the user presses Update now,
and the installer asks before replacing anything. Favorites, history and settings live in the user's profile.
"""
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

REPO = "universalone/echoforge-retro-gaming"
API = os.environ.get("EF_GH_API") or "https://api.github.com"  # EF_GH_API: a test feed (dev aid)
INSTALLER = re.compile(r"^EchoForge-Retro-Gaming-Setup-(\d+\.\d+\.\d+)\.exe$", re.I)
UA = {"User-Agent": "EchoForge Retro Gaming", "Accept": "application/vnd.github+json"}


def cmp_version(a, b):
    """'2.10.0' is newer than '2.9.0': compares each number, not the text."""
    pa = [int(x) for x in str(a).lstrip("vV").split(".")]
    pb = [int(x) for x in str(b).lstrip("vV").split(".")]
    n = max(len(pa), len(pb))
    pa, pb = pa + [0] * (n - len(pa)), pb + [0] * (n - len(pb))
    return (pa > pb) - (pa < pb)


def newest(releases):
    """The newest published release with an installer that has a checksum. Drafts and pre-releases are skipped."""
    best = None
    for r in releases if isinstance(releases, list) else []:
        if r.get("draft") or r.get("prerelease"):
            continue
        a = next((x for x in r.get("assets") or [] if INSTALLER.match(x.get("name", ""))), None)
        if not a or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", a.get("digest") or ""):
            continue
        version = INSTALLER.match(a["name"]).group(1)
        if not best or cmp_version(version, best["version"]) > 0:
            best = {"version": version, "page": r.get("html_url", ""), "url": a.get("browser_download_url", ""),
                    "name": a["name"], "size": a.get("size") or 0, "sha256": a["digest"][7:].lower(),
                    "notes": str(r.get("body") or "")[:2000]}
    return best


def check(current, fetch=None):
    try:
        if fetch:
            releases = fetch()
        else:
            req = urllib.request.Request(f"{API}/repos/{REPO}/releases?per_page=10", headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                releases = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "GitHub is limiting requests right now. Try again in an hour." if e.code in (403, 429)
                else f"GitHub answered {e.code}."}
    except (OSError, ValueError) as e:
        return {"ok": False, "error": f"Couldn't reach GitHub ({e})."}
    best = newest(releases)
    return {"ok": True, "current": current, "latest": best, "update": bool(best) and cmp_version(best["version"], current) > 0}


def download(rel, folder, progress=lambda pct: None, opener=urllib.request.urlopen):
    """Downloads the installer and checks it; returns its path. A mismatch is deleted and refused."""
    if not INSTALLER.match(rel.get("name") or ""):
        raise ValueError("That isn't an EchoForge Retro Gaming installer.")
    if not str(rel.get("url", "")).startswith("https://github.com/"):
        raise ValueError("Updates only come from GitHub.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / rel["name"]
    part = dest.with_name(dest.name + ".part")
    h, got = hashlib.sha256(), 0
    with opener(urllib.request.Request(rel["url"], headers={"User-Agent": UA["User-Agent"]}), timeout=60) as r, part.open("wb") as out:
        while chunk := r.read(1024 * 1024):
            out.write(chunk)
            h.update(chunk)
            got += len(chunk)
            progress(min(99, round(got * 100 / (rel.get("size") or got))))
    if h.hexdigest() != rel["sha256"]:
        part.unlink(missing_ok=True)
        raise ValueError("The download doesn't match the checksum GitHub published, so it was deleted.")
    part.replace(dest)
    progress(100)
    return dest
