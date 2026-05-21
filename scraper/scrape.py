"""
UFO Tracker scraper
-------------------
Downloads the Department of War PURSUE CSV release files, scrapes the
landing page for slideshow images, detects new/changed entries vs. the
previous run, translates English fields to Traditional Chinese via
deep-translator (Google) incrementally, and writes ../data.json for the
static site to consume.

Designed to run inside GitHub Actions on a daily schedule.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from deep_translator import GoogleTranslator
    TRANSLATE_AVAILABLE = True
except Exception:  # pragma: no cover
    TRANSLATE_AVAILABLE = False

# ---------------------------------------------------------------------------

BASE = "https://www.war.gov"
INDEX_URL = f"{BASE}/UFO/"
CSV_URL_TMPL = f"{BASE}/Portals/1/Interactive/2026/UFO/uap-release{{n:03d}}.csv"
MAX_RELEASES_TO_PROBE = 50

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "scraper" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = CACHE_DIR / "state.json"
TRANSLATIONS_PATH = CACHE_DIR / "translations.json"
OUT_PATH = ROOT / "data.json"

BASE_CATEGORIES = ["UAP", "UFO", "UMA", "Drone", "Balloon"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.war.gov/",
}

# ---------------------------------------------------------------------------
# I/O helpers

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )


def http_get(url: str, *, timeout: int = 60) -> Optional[requests.Response]:
    """Fetch URL. Tries direct first, falls back to allorigins.win proxy
    when the target blocks our IP (common with .gov sites against cloud IPs)."""
    from urllib.parse import quote

    candidates = [
        url,
        f"https://api.allorigins.win/raw?url={quote(url, safe='')}",
        f"https://corsproxy.io/?{quote(url, safe='')}",
    ]

    last_err = None
    for variant in candidates:
        for attempt in range(2):
            try:
                r = requests.get(variant, headers=HEADERS, timeout=timeout)
                if r.status_code == 404:
                    return None
                if r.status_code == 403:
                    last_err = f"403 on {variant}"
                    break  # try next proxy
                r.raise_for_status()
                # allorigins sometimes returns 200 with an HTML error page;
                # treat empty/very-small text responses as failure for non-CSV URLs
                if len(r.content) < 50 and "csv" not in url.lower():
                    last_err = f"empty body via {variant}"
                    break
                return r
            except requests.RequestException as e:
                last_err = str(e)
                if attempt == 1:
                    break
                time.sleep(2)

    print(f"  ! GET failed for {url}: {last_err}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# CSV parsing

HEADER_ALIASES = {
    "title": "title",
    "name": "title",
    "subject": "title",
    "incident": "title",
    "agency": "agency",
    "originating agency": "agency",
    "originator": "agency",
    "release": "release",
    "release number": "release",
    "tranche": "release",
    "date": "incident_date",
    "incident date": "incident_date",
    "date of incident": "incident_date",
    "location": "incident_location",
    "incident location": "incident_location",
    "type": "type",
    "category": "type",
    "description": "description",
    "summary": "description",
    "narrative": "description",
    "abstract": "description",
    "file": "file_url",
    "file url": "file_url",
    "url": "file_url",
    "link": "file_url",
    "document": "file_url",
    "media": "file_url",
    "image": "image_url",
    "image url": "image_url",
    "thumbnail": "image_url",
    "video": "video_url",
    "video url": "video_url",
}


def normalise_header(h: str) -> str:
    key = re.sub(r"[^a-z0-9 ]+", "", h.lower()).strip()
    return HEADER_ALIASES.get(key, key.replace(" ", "_"))


def parse_csv(text: str, release_number: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        raw_headers = next(reader)
    except StopIteration:
        return rows
    headers = [normalise_header(h) for h in raw_headers]

    for raw in reader:
        if not any(c.strip() for c in raw):
            continue
        item: Dict[str, Any] = {}
        for h, v in zip(headers, raw):
            v = (v or "").strip()
            if h in item and v:
                item[h] = f"{item[h]} | {v}"
            else:
                item[h] = v
        item.setdefault("release", f"Release {release_number:02d}")
        rows.append(item)
    return rows


# ---------------------------------------------------------------------------
# Landing-page scrape

def scrape_landing_images(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    images: List[Dict[str, str]] = []
    seen: set = set()
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        if not src:
            continue
        if "/UFO/Slideshow" not in src and "uap" not in src.lower():
            continue
        url = urljoin(INDEX_URL, src)
        if url in seen:
            continue
        seen.add(url)
        images.append({"url": url, "alt": (img.get("alt") or "").strip()})
    return images


# ---------------------------------------------------------------------------
# Categorisation

KEYWORD_TAGS = {
    "UAP": ["uap", "anomalous"],
    "UFO": ["ufo", "unidentified flying"],
    "UMA": ["uma", "unidentified maritime", "underwater"],
    "Drone": ["drone", "uas", "unmanned aerial"],
    "Balloon": ["balloon"],
}


def categorise(item: Dict[str, Any]) -> List[str]:
    """Derive tags from the row's Type column + keyword sniffing on title/desc.
    Preserves all-caps acronyms (UAP, UFO, UMA) and dedups case-insensitively.
    """
    tags: List[str] = []
    haystack = " ".join(
        str(item.get(k, "")) for k in ("type", "title", "description")
    ).lower()

    for tag, needles in KEYWORD_TAGS.items():
        if any(n in haystack for n in needles):
            tags.append(tag)

    raw_type = (item.get("type") or "").strip()
    if raw_type:
        if raw_type.isalpha() and raw_type.isupper() and len(raw_type) <= 4:
            t = raw_type
        else:
            t = raw_type.title()
        if not any(existing.lower() == t.lower() for existing in tags):
            tags.append(t)

    return tags or ["Uncategorised"]


# ---------------------------------------------------------------------------
# Translation

def get_translator():
    if not TRANSLATE_AVAILABLE:
        return None
    try:
        return GoogleTranslator(source="en", target="zh-TW")
    except Exception as e:
        print(f"  ! Could not init translator: {e}", file=sys.stderr)
        return None


def translate_strings(strings: List[str], cache: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    to_do: List[str] = []
    for s in strings:
        if not s or not s.strip():
            out[s] = s
        elif s in cache:
            out[s] = cache[s]
        else:
            to_do.append(s)

    if not to_do:
        return out

    tr = get_translator()
    if tr is None:
        for s in to_do:
            out[s] = s
        return out

    for s in to_do:
        try:
            if len(s) > 4500:
                chunks = [s[i:i + 4500] for i in range(0, len(s), 4500)]
                translated = "".join(tr.translate(c) or "" for c in chunks)
            else:
                translated = tr.translate(s) or s
        except Exception as e:
            print(f"  ! translate failed ({len(s)} chars): {e}", file=sys.stderr)
            translated = s
        out[s] = translated
        cache[s] = translated
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------------------
# Main

def make_entry_id(item: Dict[str, Any], release_number: int, idx: int) -> str:
    fid = item.get("file_url") or item.get("video_url") or item.get("image_url")
    if fid:
        return re.sub(r"[^a-zA-Z0-9_-]+", "_", fid)[-120:]
    base = "|".join(
        str(item.get(k, "")) for k in ("title", "incident_date", "incident_location", "agency")
    )
    return f"r{release_number:03d}_i{idx:04d}_{abs(hash(base)) % 10**10}"


def run() -> int:
    print(f"== UFO Tracker scrape @ {datetime.now(timezone.utc).isoformat()} ==")

    state = load_json(STATE_PATH, {"known_ids": [], "last_run": None})
    translations = load_json(TRANSLATIONS_PATH, {})
    known_ids = set(state.get("known_ids", []))

    print("Fetching landing page...")
    landing = http_get(INDEX_URL)
    landing_html = landing.text if landing else ""
    slideshow = scrape_landing_images(landing_html) if landing_html else []
    print(f"  slideshow images: {len(slideshow)}")

    entries: List[Dict[str, Any]] = []
    for n in range(1, MAX_RELEASES_TO_PROBE + 1):
        url = CSV_URL_TMPL.format(n=n)
        r = http_get(url)
        if r is None:
            if n == 1:
                print(f"  ! release {n:03d} unavailable, stopping probe")
            break
        text = r.content.decode("utf-8-sig", errors="replace")
        rows = parse_csv(text, n)
        print(f"  release {n:03d}: {len(rows)} rows")
        for row in rows:
            row["__release_n"] = n
            row["__source_csv"] = url
            entries.append(row)
        time.sleep(0.5)

    new_ids: List[str] = []
    normalised: List[Dict[str, Any]] = []
    for idx, row in enumerate(entries):
        entry_id = make_entry_id(row, row.get("__release_n", 0), idx)

        image_urls: List[str] = []
        for k, v in row.items():
            if not isinstance(v, str):
                continue
            for tok in re.findall(r"https?://[^\s,;]+", v):
                if re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|$)", tok, re.I):
                    image_urls.append(tok)

        title = (row.get("title") or row.get("incident_location") or row.get("type")
                 or "Unidentified record")
        description = row.get("description") or row.get("narrative") or ""

        n_entry = {
            "id": entry_id,
            "title_en": title,
            "description_en": description,
            "agency": row.get("agency") or "",
            "release": row.get("release") or f"Release {row.get('__release_n', 0):02d}",
            "release_n": row.get("__release_n", 0),
            "incident_date": row.get("incident_date") or "",
            "incident_location": row.get("incident_location") or "",
            "type": row.get("type") or "",
            "file_url": row.get("file_url") or "",
            "video_url": row.get("video_url") or "",
            "image_urls": list(dict.fromkeys(image_urls)),
            "source_csv": row.get("__source_csv") or "",
            "tags": categorise(row),
        }
        normalised.append(n_entry)
        if entry_id not in known_ids:
            new_ids.append(entry_id)

    print(f"Translating ({len(normalised)} entries, {len(new_ids)} new)...")
    strings_to_translate: List[str] = []
    for e in normalised:
        for k in ("title_en", "description_en", "agency", "incident_location", "type"):
            v = e.get(k) or ""
            if v:
                strings_to_translate.append(v)
    strings_to_translate = list(dict.fromkeys(strings_to_translate))
    translations_used = translate_strings(strings_to_translate, translations)
    save_json(TRANSLATIONS_PATH, translations)

    for e in normalised:
        e["title_zh"] = translations_used.get(e["title_en"], e["title_en"])
        e["description_zh"] = translations_used.get(e["description_en"], e["description_en"])
        e["agency_zh"] = translations_used.get(e["agency"], e["agency"])
        e["incident_location_zh"] = translations_used.get(e["incident_location"], e["incident_location"])
        e["type_zh"] = translations_used.get(e["type"], e["type"])

    all_tags = set(BASE_CATEGORIES)
    for e in normalised:
        all_tags.update(e["tags"])

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": INDEX_URL,
        "has_new_today": len(new_ids) > 0,
        "new_count": len(new_ids),
        "new_ids": new_ids,
        "previous_run_at": state.get("last_run"),
        "categories": sorted(all_tags),
        "slideshow": slideshow,
        "entries": normalised,
        "totals": {
            "entries": len(normalised),
            "translations_cached": len(translations),
        },
    }
    save_json(OUT_PATH, output)
    print(f"Wrote {OUT_PATH}  entries={len(normalised)}  new={len(new_ids)}")

    state["known_ids"] = sorted(known_ids.union({e["id"] for e in normalised}))
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_json(STATE_PATH, state)

    return 0


if __name__ == "__main__":
    sys.exit(run())
