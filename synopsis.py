"""Game synopses from Wikipedia, plus year, genre, developer and publisher from Wikidata.

Only the game's name and the words "video game" (or the system's name) are sent. Wikipedia's text is CC BY-SA,
so the game page links back to the article. Same matching rules as EchoForge's app/synopsis.js.
"""
import json
import re
import unicodedata
import urllib.parse
import urllib.request

UA = {"User-Agent": "EchoForge Retro Gaming (https://github.com/universalone/echoforge-retro-gaming)"}
WP = "https://en.wikipedia.org/w/api.php?"
WD = "https://www.wikidata.org/w/api.php?"
ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10"}
NOT_GAME = re.compile(r"franchise|series|character|media|company|developer|console|engine|soundtrack|film|novel", re.I)
GENRE = re.compile(r"game|shooter|racing|racer|platform|simulat|puzzle|fighting|beat|role-playing|adventure|strategy|sports|"
                   r"horror|stealth|rhythm|party|survival|hack and slash|open world", re.I)


def key(s):
    """Loose name key: no tags, Æ -> ae, "Title, The" -> "The Title", no articles, only letters and digits."""
    s = str(s or "").lower().replace("æ", "ae").replace("œ", "oe")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s)
    s = re.sub(r"^(.*?),\s*the\b", r"the \1", s)
    s = s.replace("&", " and ").replace("™", "").replace("®", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(the|a|an)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def words(s):
    return [ROMAN.get(w, w) for w in key(s).split()]


def nums(t):
    return " ".join(x for x in t.split() if x.isdigit())


def is_game(d):
    return bool(re.search(r"\bgame\b", d or "", re.I)) and not NOT_GAME.search(d or "")


def pick(pages, names, system_name=""):
    """The article for a game from Wikipedia's search results, or None. A name that doesn't match is refused,
    so a short name never gets another game's article and a sequel never stands in for the first game."""
    wanted = [w for w in (words(n) for n in names) if w]
    if not wanted:
        return None
    scored = []
    for p in sorted(pages or [], key=lambda p: p.get("index", 0)):
        if not is_game(p.get("description")) or p.get("title", "").lower().startswith("list of") or not p.get("extract"):
            continue
        t = " ".join(words(p["title"]))
        score = 0
        for w in wanted:
            n = " ".join(w)
            if t == n:
                score = max(score, 3)
            elif len(w) > 1 and (t.startswith(n + " ") or n.startswith(t + " ")) and min(len(t), len(n)) >= 6 \
                    and not (t[len(n):] if len(t) > len(n) else n[len(t):]).strip()[:1].isdigit():
                score = max(score, 2)  # a subtitle added or missing, never a sequel number
            elif len(w) > 1 and all(x in t.split() for x in w) and nums(t) == nums(n):
                score = max(score, 1)
        if score:
            scored.append((score, p))
    if not scored:
        return None
    top = max(sc for sc, _ in scored)
    tied = [p for sc, p in scored if sc == top]
    # Same name (an original and its remake): the one that mentions the console, then the oldest.
    sys_words = [w for w in re.split(r"[()]", system_name or "") if w.strip()]

    def rank(p):
        mentions = any(w.strip().lower() in p.get("extract", "").lower() for w in sys_words)
        year = re.search(r"\b(?:19|20)\d\d\b", p.get("description") or "")
        return (0 if mentions else 1, int(year.group(0)) if year else 9999)
    return min(tied, key=rank)


def trim(text, limit=900):
    """The first paragraph or two, cut at a sentence end. Empty pronunciation brackets are removed."""
    text = re.sub(r"\s*\(\s*[;,]?\s*\)", "", str(text or ""))
    out = ""
    for p in (x.strip() for x in text.split("\n")):
        if not p:
            continue
        if out and len(out + "\n\n" + p) > limit:
            break
        out = out + "\n\n" + p if out else p
    if len(out) > limit:
        cut = out[:limit]
        end = max(cut.rfind(". "), cut.rfind(".\n"))
        out = cut[:end + 1] if end > 200 else cut.rstrip() + "…"
    return out


def first_year(times):
    years = sorted(int(m.group(1)) for m in (re.match(r"^[+-]?(\d{4})", str(t)) for t in times or []) if m)
    return years[0] if years else None


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def facts(qid, get=get_json):
    if not re.fullmatch(r"Q\d+", qid or ""):
        return {}
    e = get(WD + urllib.parse.urlencode({"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"}))
    claims = ((e.get("entities") or {}).get(qid) or {}).get("claims") or {}

    def ids(p):
        out = []
        for c in claims.get(p, []):
            v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            if isinstance(v, dict) and v.get("id"):
                out.append(v["id"])
        return out[:3]

    groups = {"genre": ids("P136"), "dev": ids("P178"), "pub": ids("P123")}
    times = [(((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("time") for c in claims.get("P577", [])]
    out = {}
    year = first_year([t for t in times if t])
    if year:
        out["year"] = year
    every = list(dict.fromkeys(i for v in groups.values() for i in v))
    labels = {}
    if every:
        l = get(WD + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(every), "props": "labels",
                                             "languages": "en", "format": "json"}))
        for i, v in (l.get("entities") or {}).items():
            en = (v.get("labels") or {}).get("en")
            if en:
                labels[i] = en["value"]
    for k, v in groups.items():
        names = [labels[i] for i in v if i in labels]
        if names:
            out[k] = names
    if out.get("genre"):  # skip themes like "crossover fiction"
        g = [n for n in out["genre"] if GENRE.search(n)]
        out["genre"] = (g or out["genre"])[:2]
    return out


def search(q, get=get_json):
    j = get(WP + urllib.parse.urlencode({"action": "query", "generator": "search", "gsrsearch": q, "gsrlimit": "8",
                                         "prop": "description|extracts|pageprops", "exintro": "1", "explaintext": "1",
                                         "exlimit": "max", "ppprop": "wikibase_item", "redirects": "1", "format": "json",
                                         "formatversion": "2"}))
    return (j.get("query") or {}).get("pages") or []


def lookup(names, system_name="", get=get_json):
    """names: the game's title first, then other spellings. Returns a dict with ok, text, title, url, year, genre, dev, pub."""
    clean = list(dict.fromkeys(str(n or "").strip() for n in names or [] if key(n)))[:3]
    if not clean:
        return {"ok": False, "reason": "noname"}
    page = None
    for n in clean:
        page = pick(search(f"{key(n)} video game", get), clean, system_name)
        if not page and system_name:
            page = pick(search(f"{key(n)} {system_name} game", get), clean, system_name)
        if page:
            break
    if not page:
        return {"ok": False, "reason": "nomatch"}
    text = trim(page["extract"])
    if not text:
        return {"ok": False, "reason": "nomatch"}
    try:
        extra = facts((page.get("pageprops") or {}).get("wikibase_item"), get)
    except (OSError, ValueError):
        extra = {}
    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_"), safe="")
    return {"ok": True, "text": text, "title": page["title"], "url": url, **extra}
