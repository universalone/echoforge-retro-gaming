"""Tests synopsis.py with made-up Wikipedia and Wikidata answers (no internet needed).
Run: python -I tests/test_synopsis.py"""
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import synopsis as S  # noqa: E402

fails = 0


def check(name, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
    fails += 0 if ok else 1


def page(index, title, description, extract, qid=None):
    return {"index": index, "title": title, "description": description, "extract": extract,
            **({"pageprops": {"wikibase_item": qid}} if qid else {})}


MARIO = [page(1, "Super Mario Bros. 3 (album)", "Album", "An album.", "Q1"),
         page(2, "Super Mario Bros.", "1985 video game", "Super Mario Bros. is a 1985 platform game.", "Q2"),
         page(3, "Super Mario Bros. 3", "1988 video game", "Super Mario Bros. 3 is a 1988 platform game.\nIt was released for the NES.", "Q3")]
ZELDA = [page(1, "Zelda: Ocarina (2026 video game)", "2026 video game", "A remake for a new console.", "Q4"),
         page(2, "Zelda: Ocarina", "1998 video game", "A game for the Nintendo 64.", "Q5")]

check("Æ, punctuation and “The” don’t matter", S.key("Æon Flux") == "aeon flux"
      and S.key("Legend of Zelda, The - Ocarina (USA)") == S.key("The Legend of Zelda: Ocarina"))
check("Roman numerals match digits", S.words("Final Fight III") == S.words("Final Fight 3"))
check("the right game, not an album or the first game", S.pick(MARIO, ["Super Mario Bros. 3"])["title"] == "Super Mario Bros. 3")
check("a sequel isn’t the first game", S.pick([page(1, "Mega Man 2", "1988 video game", "x")], ["Mega Man"]) is None)
check("a game whose name doesn’t match gets nothing", S.pick(MARIO, ["Contra"]) is None)
check("one word in common isn’t a match", S.pick([page(1, "Black Tiger", "1987 video game", "x")], ["Black"]) is None)
check("an original beats its remake", S.pick(ZELDA, ["Zelda Ocarina"], "Nintendo 64")["description"] == "1998 video game")
check("films and lists are skipped", S.pick([page(1, "Mortal Kombat (film)", "1995 film", "x"), page(2, "List of Mortal Kombat games", "", "x")], ["Mortal Kombat"]) is None)
long = " ".join(f"Sentence number {i} is here." for i in range(30))
t = S.trim(long + "\n" + long)
check("long text is cut at a sentence end", len(t) <= 900 and t.endswith("."), len(t))
check("keeps two short paragraphs", S.trim("One.\nTwo.\nThree is long. " + "x" * 900) == "One.\n\nTwo.")
check("earliest release year", S.first_year(["+1989-04-21T00:00:00Z", "+1988-10-23T00:00:00Z"]) == 1988)

urls = []


def fake(url):
    urls.append(url)
    u = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(u.query))
    if u.netloc == "en.wikipedia.org":
        return {"query": {"pages": MARIO if "mario" in q["gsrsearch"] else []}}
    if q.get("props") == "claims":
        snak = lambda v: {"mainsnak": {"datavalue": {"value": v}}}  # noqa: E731
        return {"entities": {"Q3": {"claims": {"P136": [snak({"id": "Q10"}), snak({"id": "Q11"})], "P178": [snak({"id": "Q12"})],
                                               "P577": [snak({"time": "+1990-02-12T00:00:00Z"}), snak({"time": "+1988-10-23T00:00:00Z"})]}}}}
    return {"entities": {"Q10": {"labels": {"en": {"value": "crossover fiction"}}}, "Q11": {"labels": {"en": {"value": "platform game"}}},
                         "Q12": {"labels": {"en": {"value": "Nintendo EAD"}}}}}


r = S.lookup(["Super Mario Bros. 3", "Super Mario Bros. 3 (USA) (Rev 1)"], "Nintendo Entertainment System", fake)
check("finds the article", r["ok"] and r["title"] == "Super Mario Bros. 3" and r["url"] == "https://en.wikipedia.org/wiki/Super_Mario_Bros._3", r.get("url"))
check("year, genre and developer", r["year"] == 1988 and r["genre"] == ["platform game"] and r["dev"] == ["Nintendo EAD"])
check("only the game’s name is sent", dict(urllib.parse.parse_qsl(urllib.parse.urlparse(urls[0]).query))["gsrsearch"] == "super mario bros 3 video game")
urls.clear()
miss = S.lookup(["Contra"], "Nintendo Entertainment System", fake)
check("no match says so, after asking with the system", not miss["ok"] and any("Nintendo+Entertainment+System" in u for u in urls))
check("no name, no search", S.lookup(["", " "], "", fake)["reason"] == "noname")
print(f"{fails} FAILED" if fails else "ALL PASSED")
sys.exit(1 if fails else 0)
