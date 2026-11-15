# Dad's Bookshelf

A lifelong personal book review site, catalogued from 2009 and updated monthly. It exists to leave something for his kids, and they are the reason behind all of it.

**Live site:** https://jackkruseiii.github.io/dadsbookshelf/
**Repo:** https://github.com/jackkruseiii/dadsbookshelf (note: `dadsbookshelf`, no hyphen)

Full reviews live on the author's blogs, which every card links back to:

- https://kruzoo.blogspot.com
- https://fuuo.blogspot.com

## How it's built

`books.json` holds every book. A build script turns it into the site. Nothing generated is edited by hand.

| File | Role |
|---|---|
| `books.json` | **The master data file.** One entry per book (ids 1-329, 328 entries; id 284 intentionally absent). |
| `build.py` | Checks `books.json` (parses, unique ids, themes, links) and writes the whole site. Review text is copied character for character; the build never writes or rewords anything. |
| `covers.py` | Finds cover art on Open Library and remembers it in `covers.json`. Runs on GitHub only. |
| `covers.json` | Cover lookup cache (not book data). To fix a wrong cover, set its `"cover"` number (or `null`) and add `"locked": true`. |
| `site-src/` | The design: `site.css`, `site.js`, and the suggestion form. Edit here. |
| `index.html`, `book/`, `assets/`, `search.json`, `sitemap.xml` | **Generated.** Never edit by hand; rerun `python3 build.py`. |
| `.github/workflows/build.yml` | On every push that changes the data or design, GitHub finds covers for new books and rebuilds. |
| `og-image.png` | 1200x630 social preview image. |

What the site does:

- **One real page per book** (`book/<id>-<title>/`) with its own title, description and share-preview tags.
- **Search reads everything**: titles, authors, countries, themes, years, and the full text of the notes and quotes, with filters and sorting. Every search and filter has its own address.
- **Old links still work**: `?book=<id>` opens that book.

`python3 build.py --preview` builds a trial copy into `v2/` (not committed) for trying design changes.

The site was rebuilt on 2026-11-15. The previous single-page version is in the git history at commit `5a258b6`.

**Id 284 is intentionally absent.** Do not "fix" the gap or renumber. New entries take the next id after the highest in use.

**Re-reads are separate entries on purpose.** *One Thousand Gifts* appears twice (2011 and 2014) because it was read twice. Do not merge or remove it as a duplicate.

## books.json is the single source of truth

Everything on the site comes from `books.json`. Other files are not authoritative:

- `Dads_Bookshelf_Master.xlsx` and `greats_reviews.json` are retired. They are not used and are not kept in sync. Do not read from them or update them.

When in doubt, `books.json` wins.

## Monthly update workflow

`books.json` is never edited by hand. Updates are done by asking Claude, which edits the file, checks it, and pushes.

1. **Publish the new review** on kruzoo or fuuo as usual.
2. **Give Claude the link(s)** to the new post(s), plus anything not in the post (rating, theme, year read, whether it is an all-time "great").
3. **Claude builds the entry** from the author's own words in the linked review (see rules below) and assigns the next unused id.
4. **Claude runs `python3 build.py`**, which validates `books.json` (parses, ids unique) and regenerates the pages.
5. **Claude commits `books.json` and the generated pages in one commit and pushes** to `main`. GitHub then looks up the cover for any new book, rebuilds, and Pages redeploys within a few minutes. Claude pulls that rebuild before the next edit.
6. **Spot-check the live site** and read any new card once for flow.

Session notes for Claude:

- Pushing requires attaching the repo with push access (`add_repo` with access `push`).
- Blog text can only be fetched in short verbatim pieces (about 125 characters at a time) with WebFetch. The shell cannot reach blogspot.

## Content rules (non-negotiable)

1. **Only the author's own words appear in reviews.** Claude never writes or paraphrases a review. Card excerpts are verbatim fragments from his posts, joined with an ellipsis ("…") where text is skipped.
2. **Each card carries a quote from the actual book** when one appears in his linked review. If his posts contain no book quote, the card has none rather than a substituted one.
3. **Quotes must be the book's words**, not the author's own sentences from his review. Quotes from someone other than the book's author (for example a blurb or a letter) are credited through the `quoteSources` field.
4. **Quote-only "greats"** (no summary available in his words) render as quote-only cards. That is intended.
5. **Every card links to the original post.** Fix the link rather than leave a dead or generic one.

## Known open items

- Some books still have no note/summary or no rating.
- About 64 books have no cover on Open Library and show a typeset cover instead.
