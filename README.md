# Dad's Bookshelf

A lifelong personal book review site, catalogued from 2009 and updated monthly. It exists to leave something for his kids, and they are the reason behind all of it.

**Live site:** https://jackkruseiii.github.io/dadsbookshelf/
**Repo:** https://github.com/jackkruseiii/dadsbookshelf (note: `dadsbookshelf`, no hyphen)

Full reviews live on the author's blogs, which every card links back to:

- https://kruzoo.blogspot.com
- https://fuuo.blogspot.com

## How it's built

Two files do all the work (plus a social preview image). There is no build step.

| File | Role |
|---|---|
| `index.html` | All page logic and CSS. Loads `books.json` and renders the cards. |
| `books.json` | **The master data file.** One entry per book (ids 1-307, 306 entries). |
| `og-image.png` | 1200x630 social preview image referenced by the og/twitter tags. |

**Id 284 is intentionally absent.** Do not "fix" the gap or renumber. New entries take the next id after the highest in use.

**Re-reads are separate entries on purpose.** *One Thousand Gifts* appears twice (2011 and 2014) because it was read twice. Do not merge or remove it as a duplicate.

## books.json is the single source of truth

Everything on the site comes from `books.json`. Other files are not authoritative:

- `Dads_Bookshelf_Master.xlsx` is out of date. It does not contain the Achebe entries, *A Personal Matter*, or the *Hamnet* typo fix.
- `greats_reviews.json` is stale and should not be used to update the site.

When in doubt, `books.json` wins.

## Monthly update workflow

`books.json` is never edited by hand. Updates are done by asking Claude, which edits the file, checks it, and pushes.

1. **Publish the new review** on kruzoo or fuuo as usual.
2. **Give Claude the link(s)** to the new post(s), plus anything not in the post (rating, theme, year read, whether it is an all-time "great").
3. **Claude builds the entry** from the author's own words in the linked review (see rules below) and assigns the next unused id.
4. **Claude validates** that `books.json` still parses, ids are unique, and no entry is missing a link, rating, or note.
5. **Claude commits and pushes** to `main`. GitHub Pages redeploys on its own within a minute or two.
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
- The "Beyond Achebe" badge sends `?country=<Name>#atlas`, but beyondachebe.com does not read `?country=` yet, so the link lands on the atlas section.
- `Dads_Bookshelf_Master.xlsx` and `greats_reviews.json` still need to be brought in line with `books.json` (or retired).
