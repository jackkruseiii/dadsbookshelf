#!/usr/bin/env python3
"""
Dad's Bookshelf - cover copier.

Downloads every cover listed in covers.json into this repo, so the site serves
its own copies and never depends on Open Library's (or Amazon's) image servers
being up. Runs on GitHub (see .github/workflows/build.yml); safe to re-run -
files already saved are skipped, failures are simply retried next run.

    covers/ol/<number>.jpg   Open Library covers
    covers/url/<id>.jpg      covers that came from a "url" in covers.json
"""
import json, pathlib, time, urllib.request

HERE = pathlib.Path(__file__).parent
UA = {"User-Agent": "DadsBookshelf-cover-copier (jackkruseiii.github.io/dadsbookshelf)"}


def fetch(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) > 1000 and data[:2] == b"\xff\xd8":
                return data
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def main():
    covers = json.loads((HERE / "covers.json").read_text(encoding="utf-8"))
    saved = skipped = failed = 0
    for key, v in covers.items():
        if v.get("file"):
            continue
        if v.get("cover"):
            url = f"https://covers.openlibrary.org/b/id/{int(v['cover'])}-L.jpg?default=false"
            dest = HERE / "covers" / "ol" / f"{int(v['cover'])}.jpg"
        elif str(v.get("url", "")).startswith("https://"):
            url, dest = v["url"], HERE / "covers" / "url" / f"{key}.jpg"
        else:
            continue
        if dest.exists():
            skipped += 1
            continue
        data = fetch(url)
        if data is None:
            failed += 1
            print("failed:", key, url)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        saved += 1
        time.sleep(0.3)
    print(f"saved {saved}, already had {skipped}, failed {failed}")


if __name__ == "__main__":
    main()
