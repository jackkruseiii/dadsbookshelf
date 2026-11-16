#!/usr/bin/env python3
"""
Dad's Bookshelf - site builder.

books.json is the only source of truth. This script reads it, checks it, and
writes the whole site: the home page, one page per book, the search index and
the sitemap. Nothing in the output is edited by hand.

    python3 build.py              build the site into the repo root
    python3 build.py --preview    build a trial copy into ./v2 (hidden from search engines)
    python3 build.py --check      only validate books.json

Every word of review text is copied from books.json exactly as written.
The script never writes, shortens or rewords a review. Where a card or a
description shows only part of a note, it is a verbatim cut ending in "…".
"""
import argparse, html, json, re, shutil, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "site-src"
SITE_URL = "https://jackkruseiii.github.io/dadsbookshelf/"
SITE_NAME = "Dad's Bookshelf"
TAGLINE = "one shelf, since 2009"

THEMES = [
    "Christian Faith",
    "War, Service & Sacrifice",
    "Leadership & Building Things",
    "Memoir & a Life Examined",
    "Sweeping Fiction",
    "Sci-Fi & Dystopian",
    "Conflict Zones & Hard Truths",
]
# Theme intros and page copy below are carried over word for word from the
# original index.html.
THEME_INTROS = {
    "Christian Faith": "Books that shaped how I think about belief, grace, and the actual practice of following Jesus — not the tidy version, the lived one.",
    "War, Service & Sacrifice": "Written by and about people who served. The cost of it, the weight of command, and what the after-action report leaves out.",
    "Leadership & Building Things": "On running organizations, building habits, and doing hard, slow work well — in uniform and out of it.",
    "Memoir & a Life Examined": "Lives told plainly. Biography, memoir, and the non-fiction that reads like someone leveling with you.",
    "Sweeping Fiction": "Novels with real scope — historical canvases, family sagas, and stories that earn their length.",
    "Sci-Fi & Dystopian": "Science fiction and dystopian futures. Worlds built sideways from this one.",
    "Conflict Zones & Hard Truths": "Reporting and history from the hardest places — the kind of non-fiction that doesn't let you look away.",
}
GREATS_INTRO = "Start here. These are books that can change and shape you, alight your imagination, wreck you, and inspire you."
AUTHORS_INTRO = "Writers I've come back to more than once — the surest sign a voice actually stuck."
NO_REVIEW = "No full review on file for this one — just the record that it was read."

# ---- Beyond Achebe cross-links (same rules as the original site) ----
BA_COUNTRIES = [
    "Algeria", "Libya", "Morocco", "Tunisia", "Mauritania", "Cameroon", "Ghana", "Nigeria", "Senegal", "Togo",
    "Côte d'Ivoire", "Burkina Faso", "Liberia", "Sierra Leone", "Cabo Verde", "Mali", "Tanzania", "Kenya", "Uganda",
    "Comoros", "Sudan", "Ethiopia", "Somalia", "Eritrea", "Djibouti", "Congo (DRC)", "Congo (Republic)", "Burundi",
    "Rwanda", "Equatorial Guinea", "South Africa", "Zimbabwe", "Mozambique", "Zambia", "Malawi", "Madagascar", "Egypt",
    "Angola", "Benin", "Gambia", "Guinea", "Guinea-Bissau", "Niger", "São Tomé and Príncipe", "Seychelles", "Mauritius",
    "South Sudan", "Central African Republic", "Chad", "Gabon", "Botswana", "Eswatini", "Lesotho", "Namibia",
]
BA_ALIASES = {
    "drc": "Congo (DRC)", "dr congo": "Congo (DRC)", "democratic republic of the congo": "Congo (DRC)",
    "republic of congo": "Congo (Republic)", "ivory coast": "Côte d'Ivoire", "cape verde": "Cabo Verde",
    "swaziland": "Eswatini",
}


def fold(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("’", "'").replace("‘", "'").lower().strip()


BA_BY_NORM = {fold(c): c for c in BA_COUNTRIES}


def ba_link(country):
    name = None
    for part in re.split(r"[,/;]", str(country or "")):
        k = fold(part)
        name = BA_BY_NORM.get(k) or BA_ALIASES.get(k)
        if name:
            break
    from urllib.parse import quote
    return "https://beyondachebe.com/" + ("?country=" + quote(name) if name else "") + "#atlas"


# ---------------------------------------------------------------- helpers
def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def roman(n):
    out = ""
    for v, s in [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]:
        while n >= v:
            out += s
            n -= v
    return out


def number_word(n):
    ones = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
            "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    if not 0 <= n <= 99:
        return str(n)
    return ones[n] if n < 20 else tens[n // 10] + ("-" + ones[n % 10] if n % 10 else "")


def slugify(title):
    s = fold(title).replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60].rstrip("-") or "book"


def cut(text, limit):
    """Verbatim cut at a word break, ending in an ellipsis. Never rewords."""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    head = text[:limit]
    sp = head.rfind(" ")
    return (head[:sp] if sp > 40 else head).rstrip(" ,;:—-") + "…"


def stars(rating):
    r = int(rating or 0)
    if not r:
        return '<span class="stars">unrated</span>'
    return (f'<span class="stars" role="img" aria-label="Rated {r} out of 5">'
            f'{"★" * r}<span class="off">{"★" * (5 - r)}</span></span>')


def short_title(b):
    return re.split(r"\s*[:(]", b["title"])[0]


def greats_label(n):
    return f", {n} all-time great{'s' if n > 1 else ''}" if n else ""


def paragraphs(text):
    return "".join(f"<p>{e(p)}</p>" for p in re.split(r"\n+", text) if p.strip())


# ------------------------------------------------------------- validation
def validate(books):
    errors, warnings = [], []
    if not isinstance(books, list):
        return ["books.json must be a list of books"], []
    seen = set()
    for i, b in enumerate(books):
        tag = f"entry {i + 1} (id {b.get('id')!r}, {b.get('title')!r})"
        if not isinstance(b.get("id"), int):
            errors.append(f"{tag}: id must be a whole number")
        elif b["id"] in seen:
            errors.append(f"{tag}: duplicate id")
        seen.add(b.get("id"))
        for f in ("title", "author"):
            if not str(b.get(f) or "").strip():
                errors.append(f"{tag}: missing {f}")
        if b.get("theme") not in THEMES:
            errors.append(f"{tag}: theme {b.get('theme')!r} is not one of the seven themes")
        if not isinstance(b.get("yearRead"), int):
            errors.append(f"{tag}: yearRead must be a year")
        if b.get("rating") not in (1, 2, 3, 4, 5):
            warnings.append(f"{tag}: no rating")
        link = b.get("link")
        if link and not re.match(r"https?://", link):
            errors.append(f"{tag}: link is not a web address")
        if b.get("quoteSources") and len(b["quoteSources"]) > len(b.get("quotes") or []):
            errors.append(f"{tag}: more quoteSources than quotes")
    return errors, warnings


# --------------------------------------------------------------- the model
class Site:
    def __init__(self, books, base_url, preview, covers=None):
        self.covers = covers or {}
        self.books = books
        self.base = base_url
        self.preview = preview
        self.by_id = {b["id"]: b for b in books}
        self.greats = sorted((b for b in books if b.get("isGreat") and not b.get("isGreatDuplicate")),
                             key=lambda b: (b["yearRead"], b["title"]))
        self.great_no = {b["id"]: i + 1 for i, b in enumerate(self.greats)}
        self.slug = {b["id"]: f'{b["id"]}-{slugify(b["title"])}' for b in books}
        years = [b["yearRead"] for b in books]
        self.y0, self.y1 = min(years), max(years)
        by_author = {}
        for b in books:
            by_author.setdefault(b["author"], []).append(b)
        self.by_author = by_author
        self.authors = sorted(
            ({"name": n, "books": sorted(bs, key=lambda b: b["yearRead"]),
              "greats": sum(1 for b in bs if b.get("isGreat"))} for n, bs in by_author.items() if len(bs) >= 2),
            key=lambda a: (-len(a["books"]), -a["greats"], a["name"]))
        # reading order for previous / next
        self.order = sorted(books, key=lambda b: (b["yearRead"], b["id"]))
        self.pos = {b["id"]: i for i, b in enumerate(self.order)}

    def th(self, b):
        return THEMES.index(b["theme"])

    def quotes(self, b):
        """(text, source) pairs, following the original site's rules."""
        if b.get("isGreat") and b.get("quotes"):
            src = b.get("quoteSources") or []
            return [(q, src[i] if i < len(src) else "") for i, q in enumerate(b["quotes"])]
        return [(b["quote"], "")] if b.get("quote") else []

    def own_words(self, b):
        if b.get("isGreat") and b.get("summary"):
            return b["summary"]
        return b.get("note") or ""

    def description(self, b):
        """Facts plus a verbatim cut of his own words. Nothing is written here."""
        facts = f'{b["title"]} by {b["author"]}. Read in {b["yearRead"]}'
        if b.get("rating"):
            facts += f', rated {b["rating"]} out of 5'
        facts += "."
        own = self.own_words(b)
        return facts + (" " + cut(own, 150) if own else "")

    # ---- fragments
    def cover(self, b, extra=""):
        short = short_title(b)
        # Real cover from Open Library when covers.json has one; the typeset cover
        # underneath shows while it loads, or if it is missing.
        entry = self.covers.get(str(b["id"])) or {}
        cid = entry.get("cover")
        size = "L" if "cover-lg" in extra else "M"
        # A hand-set "url" in covers.json (any https image) is used when there is no Open Library number.
        # A "file" (e.g. covers/54.jpg, kept in the repo) wins over everything else.
        src = (self.base + entry["file"] if entry.get("file")
               else f"https://covers.openlibrary.org/b/id/{int(cid)}-{size}.jpg?default=false" if cid
               else entry.get("url") if str(entry.get("url", "")).startswith("https://") else "")
        img = (f'<img src="{e(src)}" alt="" '
               f'loading="lazy" decoding="async" onerror="this.remove()">') if src else ""
        return (f'<span class="cover th{self.th(b)}{extra}" aria-hidden="true">'
                f'<span class="cover-t">{e(short)}</span><span class="cover-a">{e(b["author"])}</span>{img}</span>')

    def item(self, b, root=""):
        g = self.great_no.get(b["id"])
        qs = self.quotes(b)
        has_words = bool(self.own_words(b))
        attrs = {
            "data-id": b["id"], "data-y": b["yearRead"], "data-p": b.get("pubYear") or 0,
            "data-r": b.get("rating") or 0, "data-g": g or 0, "data-th": self.th(b),
            "data-rg": b.get("region") or "", "data-ty": b.get("type") or "",
            "data-af": 1 if b.get("africa") else 0, "data-w": 1 if has_words else 0,
            "data-t": fold(re.sub(r"^(the|a|an)\s+", "", b["title"], flags=re.I)),
            "data-a": fold(b["author"].split()[-1] + " " + b["author"]),
        }
        a = " ".join(f'{k}="{e(v)}"' for k, v in attrs.items())
        quote = f'<span class="bk-quote">“{e(cut(qs[0][0], 150))}”</span>' if qs else ""
        badge = (f'<a class="ba" href="{e(ba_link(b.get("country")))}" target="_blank" rel="noopener" '
                 f'title="See this on Beyond Achebe">Beyond Achebe</a>') if b.get("africa") else ""
        no = f'<span class="bk-no">{roman(g)}</span>' if g else ""
        great = '<span class="bk-great">All-time great</span>' if b.get("isGreat") else ""
        return (f'<li class="bk" {a}><a class="bk-link" href="{root}book/{self.slug[b["id"]]}/">'
                f'{self.cover(b)}<span class="bk-body">{no}'
                f'<span class="bk-title">{e(b["title"])}</span>'
                f'<span class="bk-author">{e(b["author"])}</span>{quote}'
                f'<span class="bk-snip" hidden></span>'
                f'<span class="bk-meta"><span>Read {b["yearRead"]}</span>{stars(b.get("rating"))}'
                f'<span class="bk-theme">{e(b["theme"])}</span>{great}</span>'
                f'</span></a>{badge}</li>')

    # ---- pages
    def head(self, title, desc, path, root, og_type="website", jsonld=None):
        url = self.base + path
        robots = '<meta name="robots" content="noindex">\n' if self.preview else ""
        ld = (f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")}</script>\n'
              if jsonld else "")
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{robots}<meta name="theme-color" content="#1A1611">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%231A1611'/%3E%3Cpath d='M14 14h13c3 0 5 1 5 4v32c0-2-2-3-5-3H14zM50 14H37c-3 0-5 1-5 4v32c0-2 2-3 5-3h13z' fill='%23C99C3C'/%3E%3C/svg%3E">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{e(SITE_NAME)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(SITE_URL)}og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Dad's Bookshelf — one shelf, since 2009">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(SITE_URL)}og-image.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/site.css">
{ld}</head>
'''

    def header(self, root, home=False):
        banner = (f'<p class="preview-bar">This is a trial copy. '
                  f'<a href="{SITE_URL}">Open the live site</a></p>\n') if self.preview else ""
        n = len(self.books)
        return f'''{banner}<header class="site-header">
  <div class="wrap header-row">
    <a class="brand" href="{root or "./"}"><span class="brand-title">Dad's Bookshelf</span><span class="brand-sub">{TAGLINE}</span></a>
    <form class="search" role="search" action="{root or "./"}" method="get">
      <input type="hidden" name="view" value="all">
      <label class="sr" for="q">Search the shelf</label>
      <input id="q" name="q" type="search" placeholder="Search {n} books, authors, countries, reviews" autocomplete="off" enterkeyhint="search">
    </form>
  </div>
</header>
'''

    def footer(self, root, home=False):
        n, g = len(self.books), len(self.greats)
        suggest = ('<button type="button" class="linkish" onclick="openFeedback()">Suggest a book</button>' if home
                   else f'<a href="{root}#suggest">Suggest a book</a>')
        return f'''<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <span class="footer-title">Dad's Bookshelf</span>
      <p>{n} books read between {self.y0} and {self.y1}. {number_word(g).capitalize()} of them changed how I think.</p>
      {suggest}
    </div>
    <div>
      <span class="footer-head">Sibling project</span>
      <a href="https://beyondachebe.com" target="_blank" rel="noopener">Beyond Achebe — a literary atlas of Africa, {len(BA_COUNTRIES)} countries</a>
    </div>
    <div>
      <span class="footer-head">Reviews and reading lists</span>
      <a href="https://fuuo.blogspot.com" target="_blank" rel="noopener">FUUO</a>
      <a href="https://kruzoo.blogspot.com" target="_blank" rel="noopener">Kruzoo</a>
      {'<a href="https://openlibrary.org" target="_blank" rel="noopener">Cover images from Open Library</a>' if self.covers else ''}
    </div>
  </div>
</footer>
<script src="{root}assets/site.js" defer></script>
'''

    def home(self):
        books, n, g = self.books, len(self.books), len(self.greats)
        desc = (f"A personal library of every book read since {self.y0} — {g} all-time greats, "
                f"{number_word(len(THEMES))} themes, and a lifetime of reading.")
        ld = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": self.base,
              "description": desc,
              "potentialAction": {"@type": "SearchAction", "target": self.base + "?view=all&q={q}",
                                  "query-input": "required name=q"}}
        out = [self.head(f"{SITE_NAME} — Every Book Since {self.y0}", desc, "", "", jsonld=ld),
               '<body class="home">\n<a class="skip" href="#shelf">Skip to the books</a>\n', self.header("", True)]

        # view switch
        out.append(f'''<nav class="views" aria-label="Sections"><div class="wrap views-row">
  <button type="button" data-view="greats" aria-pressed="true">All-time greats <span>{g}</span></button>
  <button type="button" data-view="all" aria-pressed="false">Every book <span>{n}</span></button>
  <button type="button" data-view="authors" aria-pressed="false">Authors I return to <span>{len(self.authors)}</span></button>
</div></nav>
<main id="main">
''')
        # hero with the shelf of spines
        spines = "".join(
            f'<a class="face" href="book/{self.slug[b["id"]]}/" data-id="{b["id"]}" '
            f'aria-label="{e(b["title"])} by {e(b["author"])}">{self.cover(b)}</a>' for b in self.greats)
        out.append(f'''<section class="hero" id="hero"><div class="wrap">
  <h1>{g} all-time greats</h1>
  <p class="lede">{e(GREATS_INTRO)}</p>
  <div class="shelf" aria-label="The all-time greats, in the order I read them">{spines}</div>
</div></section>
''')
        # numbers + books per year
        africa = sum(1 for b in books if b.get("africa"))
        per_year = {y: sum(1 for b in books if b["yearRead"] == y) for y in range(self.y0, self.y1 + 1)}
        top = max(per_year.values())
        bars = "".join(
            f'<button type="button" class="bar" data-year="{y}" style="--v:{c / top:.3f}" '
            f'aria-label="{y}: {c} books"><i></i><b>{c}</b><span>’{str(y)[2:]}</span></button>'
            for y, c in per_year.items())
        out.append(f'''<section class="numbers" id="numbers" hidden><div class="wrap numbers-row">
  <dl class="facts">
    <div><dt>Books read</dt><dd>{n}</dd></div>
    <div><dt>Years</dt><dd>{self.y1 - self.y0 + 1}</dd></div>
    <div><dt>All-time greats</dt><dd>{g}</dd></div>
    <div><dt>From Africa</dt><dd>{africa}</dd></div>
  </dl>
  <div class="years" role="group" aria-label="Books read each year. Choose a year to filter.">{bars}</div>
</div></section>
''')
        # filters
        def opts(values, labels=None):
            return "".join(f'<option value="{e(v)}">{e((labels or {}).get(v, v))}</option>' for v in values)
        regions = sorted({b["region"] for b in books if b.get("region")})
        types = sorted({b["type"] for b in books if b.get("type")})
        years = [str(y) for y in range(self.y1, self.y0 - 1, -1)]
        theme_opts = "".join(f'<option value="{i}">{e(t)}</option>' for i, t in enumerate(THEMES))
        intros = "".join(f'<p class="theme-intro" data-th="{i}" hidden>{e(THEME_INTROS[t])}</p>'
                         for i, t in enumerate(THEMES))
        out.append(f'''<section class="filters" id="filters" hidden><div class="wrap">
  <details class="fdetails" id="fdetails" open><summary>Filter and sort</summary>
  <div class="filter-row">
    <label>Theme<select id="f-theme"><option value="">All themes</option>{theme_opts}</select></label>
    <label>Region<select id="f-region"><option value="">Anywhere</option>{opts(regions)}</select></label>
    <label>Type<select id="f-type"><option value="">Any type</option>{opts(types)}</select></label>
    <label>Year read<select id="f-year"><option value="">Any year</option>{opts(years)}</select></label>
    <label>Rating<select id="f-min"><option value="">Any rating</option><option value="5">5 stars</option><option value="4">4 and up</option><option value="3">3 and up</option></select></label>
    <label>Sort<select id="f-sort"><option value="recent">Most recently read</option><option value="oldest">First read</option><option value="rating">Highest rated</option><option value="title">Title A–Z</option><option value="author">Author A–Z</option><option value="pub">Newest published</option></select></label>
  </div>
  <div class="toggle-row">
    <label class="toggle"><input type="checkbox" id="f-great"> All-time greats</label>
    <label class="toggle"><input type="checkbox" id="f-africa"> Africa</label>
    <label class="toggle"><input type="checkbox" id="f-words"> Has my notes</label>
    <button type="button" class="linkish" id="f-clear" hidden>Clear filters</button>
  </div>
  </details>
  {intros}
  <p class="count" id="count" role="status" aria-live="polite"></p>
</div></section>
''')
        # the whole shelf, greats first so the page reads correctly before scripts run
        ordered = self.greats + [b for b in sorted(books, key=lambda b: (-b["yearRead"], b["title"]))
                                 if b["id"] not in self.great_no]
        out.append('<section class="wrap" id="shelf"><ul class="books view-greats" id="books">\n')
        out.extend(self.item(b) + "\n" for b in ordered)
        out.append('</ul>\n<p class="empty" id="empty" hidden>No books match. Try a shorter search, or '
                   '<button type="button" class="linkish" id="empty-clear">clear the filters</button>.</p></section>\n')
        # authors
        cards = "".join(
            f'<div class="author"><h3>{e(a["name"])}</h3>'
            f'<p class="author-n">{len(a["books"])} books{greats_label(a["greats"])}</p><ul>'
            + "".join(f'<li><a href="book/{self.slug[b["id"]]}/" data-id="{b["id"]}"><i>{e(b["title"])}</i>'
                      f'<span>{b["yearRead"]}</span></a></li>' for b in a["books"])
            + '</ul></div>' for a in self.authors)
        out.append(f'''<section class="wrap authors" id="authors" hidden>
  <h2>Authors I return to</h2>
  <p class="lede">{e(AUTHORS_INTRO)}</p>
  <div class="author-grid">{cards}</div>
</section>
</main>
''')
        out.append(self.footer("", True))
        out.append('<div class="panel-wrap" id="panel-wrap" hidden><div class="panel" id="panel" role="dialog" '
                   'aria-modal="true" aria-label="Book details" tabindex="-1"></div></div>\n')
        out.append((SRC / "feedback.html").read_text(encoding="utf-8"))
        out.append("\n</body>\n</html>\n")
        return "".join(out)

    def book_article(self, b, root):
        g = self.great_no.get(b["id"])
        qs = self.quotes(b)
        url = self.base + f'book/{self.slug[b["id"]]}/'
        parts = [f'<article class="book" id="book" data-id="{b["id"]}" data-url="{e(url)}" data-title="{e(b["title"])}">']
        parts.append(f'<div class="book-top">{self.cover(b, " cover-lg")}<div class="book-head">')
        if g:
            parts.append(f'<p class="book-no">All-time great {roman(g)} of {roman(len(self.greats))}</p>')
        elif b.get("isGreat"):
            parts.append('<p class="book-no">All-time great</p>')
        parts.append(f'<h1>{e(b["title"])}</h1><p class="book-author">'
                     f'<a href="{root}?view=all&amp;q={_q(b["author"])}">{e(b["author"])}</a></p>')
        parts.append(f'<p class="book-rating">{stars(b.get("rating"))}</p>')

        def chip(label, param, value):
            from urllib.parse import quote
            return f'<a class="chip" href="{root}?view=all&amp;{param}={quote(str(value))}">{e(label)}</a>'
        facts = [("Read", chip(b["yearRead"], "year", b["yearRead"]))]
        if b.get("rereadYears"):
            facts.append(("Read again", ", ".join(str(y) for y in b["rereadYears"])))
        if b.get("pubYear"):
            facts.append(("Published", str(b["pubYear"])))
        facts.append(("Theme", chip(b["theme"], "theme", self.th(b))))
        kinds = [k for k in (b.get("type"), b.get("secondaryType")) if k]
        if kinds:
            facts.append(("Type", " ".join(chip(k, "type", k) if k == b.get("type") else chip(k, "q", k) for k in kinds)))
        place = []
        if b.get("region"):
            place.append(chip(b["region"], "region", b["region"]))
        if b.get("country") and b["country"] != b.get("region"):
            place.append(chip(b["country"], "q", b["country"]))
        if place:
            facts.append(("Setting", " ".join(place)))
        parts.append('<dl class="book-facts">' + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)
                     + "</dl></div></div>")

        # his words, exactly as the original site chose them
        link_label = "Read my notes"
        if b.get("isGreat") and (b.get("summary") or b.get("quotes")):
            parts.append('<h2>From the shelf</h2>')
            if b.get("summary"):
                parts.append(f'<div class="words">{paragraphs(b["summary"])}</div>')
            link_label = "Read the original review"
        elif b.get("note"):
            parts.append('<h2>From the yearly reading list</h2>')
            parts.append(f'<div class="words">{paragraphs(b["note"])}</div>')
        else:
            parts.append(f'<p class="none">{e(NO_REVIEW)}</p>')
        for q, src in qs:
            cite = f'<cite>{e(src)}</cite>' if src else ""
            parts.append(f'<blockquote><p>“{e(q)}”</p>{cite}</blockquote>')
        if b.get("link"):
            parts.append(f'<p><a class="out" href="{e(b["link"])}" target="_blank" rel="noopener">{link_label}</a></p>')
        if b.get("africa"):
            parts.append(f'<div class="ba-block"><p>This book is also catalogued on Beyond Achebe, a literary atlas of Africa.</p>'
                         f'<a href="{e(ba_link(b.get("country")))}" target="_blank" rel="noopener">Open Beyond Achebe</a></div>')
        mail = ("mailto:?subject=" + _q(f'{b["title"]} — {SITE_NAME}') + "&body=" + _q(url))
        parts.append(f'<div class="share"><button type="button" data-copy>Copy link</button>'
                     f'<button type="button" data-share hidden>Share</button>'
                     f'<a href="{e(mail)}">Email</a><a class="share-full" href="{e(url)}" hidden>Open full page</a></div>')

        # more to read
        others = [x for x in self.by_author[b["author"]] if x["id"] != b["id"]]
        if others:
            parts.append(f'<h2>More by {e(b["author"])}</h2><ul class="more">' + "".join(
                f'<li><a href="{root}book/{self.slug[x["id"]]}/" data-id="{x["id"]}"><i>{e(x["title"])}</i>'
                f'<span>{x["yearRead"]}</span></a></li>' for x in sorted(others, key=lambda x: x["yearRead"])) + "</ul>")
        near = [x for x in self.greats if x["theme"] == b["theme"] and x["id"] != b["id"]
                and x["author"] != b["author"]][:4]
        if near:
            parts.append(f'<h2>All-time greats in {e(b["theme"])}</h2><ul class="more">' + "".join(
                f'<li><a href="{root}book/{self.slug[x["id"]]}/" data-id="{x["id"]}"><i>{e(x["title"])}</i>'
                f'<span>{e(x["author"])}</span></a></li>' for x in near) + "</ul>")
        parts.append("</article>")
        return "".join(parts)

    def book_page(self, b):
        root = "../../"
        path = f'book/{self.slug[b["id"]]}/'
        qs = self.quotes(b)
        ld = {"@context": "https://schema.org", "@type": "Review", "url": self.base + path,
              "author": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
              "itemReviewed": {"@type": "Book", "name": b["title"],
                               "author": {"@type": "Person", "name": b["author"]}}}
        if b.get("pubYear"):
            ld["itemReviewed"]["datePublished"] = str(b["pubYear"])
        if b.get("rating"):
            ld["reviewRating"] = {"@type": "Rating", "ratingValue": b["rating"], "bestRating": 5, "worstRating": 1}
        if self.own_words(b):
            ld["reviewBody"] = self.own_words(b)
        i = self.pos[b["id"]]
        prev = self.order[i - 1] if i > 0 else None
        nxt = self.order[i + 1] if i + 1 < len(self.order) else None
        pn = '<nav class="prevnext wrap-narrow" aria-label="Reading order">'
        pn += (f'<a href="{root}book/{self.slug[prev["id"]]}/"><span>Read before</span><i>{e(prev["title"])}</i></a>'
               if prev else "<span></span>")
        pn += (f'<a class="next" href="{root}book/{self.slug[nxt["id"]]}/"><span>Read after</span><i>{e(nxt["title"])}</i></a>'
               if nxt else "<span></span>")
        pn += "</nav>"
        return (self.head(f'{b["title"]} by {b["author"]} — {SITE_NAME}', self.description(b), path, root,
                          og_type="article", jsonld=ld)
                + '<body class="bookpage">\n' + self.header(root)
                + f'<main class="wrap-narrow"><p class="crumb"><a href="{root}">Back to the shelf</a></p>\n'
                + self.book_article(b, root) + "\n</main>\n" + pn + "\n" + self.footer(root)
                + "</body>\n</html>\n")

    def search_index(self):
        """id -> [facts, his words + book quotes]. Used only for searching."""
        idx = {}
        for b in self.books:
            facts = " ".join(str(x) for x in (b["title"], b["author"], b.get("country"), b.get("region"),
                                               b.get("type"), b.get("secondaryType"), b["theme"],
                                               b["yearRead"], b.get("pubYear")) if x)
            body = " ¶ ".join(x for x in ([self.own_words(b)] + [q for q, _ in self.quotes(b)]) if x)
            idx[str(b["id"])] = [facts, " ".join(body.split())]
        return idx


def _q(s):
    from urllib.parse import quote
    return quote(s)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="build a trial copy into ./v2")
    ap.add_argument("--check", action="store_true", help="validate books.json and stop")
    args = ap.parse_args()

    try:
        books = json.loads((HERE / "books.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        sys.exit(f"books.json does not parse: {err}")
    errors, warnings = validate(books)
    for w in warnings:
        print("note:", w)
    if errors:
        sys.exit("books.json has problems:\n  " + "\n  ".join(errors))
    print(f"books.json OK: {len(books)} books, ids unique")
    if args.check:
        return

    live = not args.preview
    out = HERE if live else HERE / "v2"
    base = SITE_URL if live else SITE_URL + "v2/"
    cpath = HERE / "covers.json"
    covers = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    site = Site(books, base, preview=not live, covers=covers)

    out.mkdir(exist_ok=True)
    if (out / "book").exists():
        shutil.rmtree(out / "book")          # drop pages for renamed or removed books
    (out / "assets").mkdir(exist_ok=True)
    css = (SRC / "site.css").read_text(encoding="utf-8") + "\n" + (SRC / "feedback.css").read_text(encoding="utf-8")
    (out / "assets" / "site.css").write_text(css, encoding="utf-8")
    shutil.copy(SRC / "site.js", out / "assets" / "site.js")
    (out / "index.html").write_text(site.home(), encoding="utf-8")
    for b in books:
        d = out / "book" / site.slug[b["id"]]
        d.mkdir(parents=True)
        (d / "index.html").write_text(site.book_page(b), encoding="utf-8")
    (out / "search.json").write_text(json.dumps(site.search_index(), ensure_ascii=False, separators=(",", ":")),
                                     encoding="utf-8")
    if live:
        urls = [base] + [base + f"book/{site.slug[b['id']]}/" for b in books]
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{html.escape(u)}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    print(f"built {len(books)} book pages + home into {out}")


if __name__ == "__main__":
    main()
