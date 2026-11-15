#!/usr/bin/env python3
"""
Dad's Bookshelf - cover finder.

Looks up each book on Open Library (title + author) and remembers the cover it
finds in covers.json. Books already in covers.json are skipped, so a normal run
only looks up new books. Runs on GitHub (see .github/workflows/build.yml).

    python3 covers.py            look up books not yet in covers.json
    python3 covers.py --retry    also retry books that had no cover last time

covers.json is a lookup cache, not book data: books.json stays the only source
of truth. To fix a wrong cover, set that book's "cover" to the right Open
Library cover number (or null for none) and add "locked": true.
"""
import difflib, json, re, sys, time, unicodedata, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = "DadsBookshelf/1.0 (https://github.com/jackkruseiii/dadsbookshelf)"
MATCHER = 3      # raise this when the matching rules change; books without a cover are then tried again


def fold(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def short_title(t):
    return re.split(r"\s*[:(]", t)[0]


def first_author(a):
    return re.split(r"\s*(?:&|,| and )\s*", a)[0].strip()


def search(params):
    q = urllib.parse.urlencode(dict(params, limit=10, fields="cover_i,title,author_name"))
    req = urllib.request.Request("https://openlibrary.org/search.json?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("docs", [])


def same_author(want, names):
    """True when the author matches, allowing for a small spelling slip or name order."""
    w = fold(want)
    for n in names:
        n = fold(n)
        if not n:
            continue
        if set(w.split()) & {x for x in n.split() if len(x) > 3}:
            return True
        if difflib.SequenceMatcher(None, w, n).ratio() >= 0.8:
            return True
        if difflib.SequenceMatcher(None, " ".join(sorted(w.split())), " ".join(sorted(n.split()))).ratio() >= 0.8:
            return True
    return False


def lookup(book):
    title, author = short_title(book["title"]), first_author(book["author"])
    want_t = fold(title)
    # 1) title + author as written   2) title only, then check the author ourselves
    for strict, params in ((False, {"title": title, "author": author}), (True, {"title": title})):
        for d in search(params):                     # Open Library's own relevance order
            got_t = fold(short_title(d.get("title", "")))
            if strict:
                title_ok = got_t == want_t
            else:
                title_ok = got_t == want_t or got_t.startswith(want_t + " ") or want_t.startswith(got_t + " ")
            if d.get("cover_i") and title_ok and same_author(author, d.get("author_name", [])):
                return {"cover": d["cover_i"], "match": d.get("title", "")}
        time.sleep(0.4)
    return {"cover": None, "v": MATCHER}


def main():
    retry = "--retry" in sys.argv
    books = json.loads((HERE / "books.json").read_text(encoding="utf-8"))
    path = HERE / "covers.json"
    covers = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    found = missed = failed = 0
    for b in books:
        key = str(b["id"])
        old = covers.get(key)
        stale = old and not old.get("cover") and old.get("v", 1) < MATCHER
        if old and (old.get("locked") or old.get("cover") or not (retry or stale)):
            continue
        for attempt in range(3):
            try:
                covers[key] = lookup(b)
                break
            except Exception as err:                 # network trouble: leave it for the next run
                time.sleep(3 * (attempt + 1))
        else:
            failed += 1
            continue
        if covers[key]["cover"]:
            found += 1
        else:
            missed += 1
            print("no cover:", b["id"], b["title"], "—", b["author"])
        time.sleep(0.5)
    ordered = {k: covers[k] for k in sorted(covers, key=int)}
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    have = sum(1 for v in ordered.values() if v.get("cover"))
    print(f"looked up: {found} found, {missed} without a cover, {failed} failed. "
          f"covers.json now has covers for {have} of {len(books)} books")


if __name__ == "__main__":
    main()
