"""Scrape the in-force EPO Guidelines for Examination (HTML-only) into a single
text file in the PART/### format that mpep_search.extract_text_from_epo_guidelines
expects.

Discovers all section URLs from any section page's embedded nav, fetches each,
and extracts the <main> content. Polite, resumable-ish, logs progress.
"""
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

YEAR = "2026"
BASE = f"https://www.epo.org/en/legal/guidelines-epc/{YEAR}/"
SEED = BASE + "a.html"
PART_TITLES = {
    "a": "Formalities examination",
    "b": "Search",
    "c": "Procedureal aspects of substantive examination",
    "d": "Opposition and limitation/revocation",
    "e": "General procedural matters",
    "f": "The European patent application",
    "g": "Patentability",
    "h": "Amendments and corrections",
}

session = requests.Session()
session.headers.update({"User-Agent": "Claude-Patent-Creator/1.0 (patent research; contact via repo)"})


def discover_urls():
    r = session.get(SEED, timeout=30)
    r.raise_for_status()
    rel = set(re.findall(r"guidelines-epc/%s/([a-h][a-z0-9_]*\.html)" % YEAR, r.text))
    return sorted(rel, key=_sort_key)


def _sort_key(fn):
    # a_ii_1_10.html -> sort by part then numeric/roman path
    stem = fn[:-5]
    parts = stem.split("_")
    out = []
    for p in parts:
        out.append((0, int(p)) if p.isdigit() else (1, p))
    return out


SHARE_RE = re.compile(r"(?:Menu\s+)?Print\s+Facebook\s+Twitter\s+Linkedin\s+Email", re.IGNORECASE)


def fetch_text(fn):
    """Return (title, body) for a section page, or None.

    EPO section pages render as: [breadcrumb] [social share bar] [title]
    Overview [title] [content]. We take everything after the share bar and
    strip the redundant leading title/"Overview" prefix.
    """
    url = BASE + fn
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            main = soup.find("main") or soup.find(attrs={"role": "main"})
            if not main:
                return None
            for bad in main.select("nav, script, style, button"):
                bad.decompose()
            h1 = main.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else fn[:-5]
            body = re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()
            m = SHARE_RE.search(body)
            if m:
                body = body[m.end():].strip()
            # Strip the redundant leading "Overview" / duplicated title prefix
            prev = None
            while prev != body:
                prev = body
                body = re.sub(r"^\s*Overview\b", "", body).strip()
                if title and body.startswith(title):
                    body = body[len(title):].strip()
            return title, body
        except Exception as e:
            if attempt == 2:
                print(f"  WARN fail {fn}: {e}", file=sys.stderr)
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def main(out_path, limit=None):
    urls = discover_urls()
    if limit:
        urls = urls[:limit]
    print(f"Discovered {len(urls)} section URLs")
    lines = []
    cur_part = None
    n_ok = 0
    for i, fn in enumerate(urls):
        part = fn[0]
        if part != cur_part:
            cur_part = part
            lines.append(f"\nPART {part.upper()} - {PART_TITLES.get(part, '').upper()}\n")
        res = fetch_text(fn)
        if res and len(res[1]) > 60:
            title, body = res
            n_ok += 1
            lines.append(f"### {title} [{fn[:-5]}]")
            lines.append(body)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(urls)} fetched ({n_ok} with content)")
        time.sleep(0.15)
    out = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote {out_path}: {len(out)} chars, {n_ok}/{len(urls)} sections with content")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "pdfs/epo_guidelines.txt"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(out, lim)
