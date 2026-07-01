#!/usr/bin/env python3
"""
Incrementally update publication citation counts.

This script preserves the existing YAML layout as much as possible:
- Field names are read case-insensitively, so title/Title/TITLE all work.
- Existing entries are updated in place by replacing or inserting only citations.
- Works missing from all files under data/publications/ can be inserted into
  the corresponding year file as review-required templates.

Optional environment variables:

  CITATION_SOURCE     Defaults to google_scholar. Use openalex to fall back to
                      the previous OpenAlex updater.
  GOOGLE_SCHOLAR_ID   Google Scholar profile ID. Defaults to GvXOVv0AAAAJ.
  SCHOLARLY_USE_FREE_PROXIES
                      Defaults to true. Uses scholarly's free proxy mode, which
                      often avoids direct Google Scholar blocking.
  OPENALEX_API_KEY    Free OpenAlex API key, if your account/API requires one.
  OPENALEX_EMAIL      Email for OpenAlex polite pool requests.
  OPENALEX_AUTHOR_ID  OpenAlex author ID, such as A1234567890. If omitted, the
                      script updates existing entries only and does not add
                      new publications, avoiding same-name author collisions.
  PUBLICATIONS_YAML   Backward-compatible path override. Defaults to
                      data/publications. If a directory is provided, all
                      *.yaml files in that directory are read and updated.
  PUBLICATIONS_DIR    Preferred path override for the publications directory.
  CITATION_META_YAML  Defaults to data/citations/meta.yaml.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import difflib
import json
import os
import re
import sys
import time


CITATION_SOURCE = os.getenv("CITATION_SOURCE", "google_scholar").strip().lower()
GOOGLE_SCHOLAR_ID = os.getenv("GOOGLE_SCHOLAR_ID", "GvXOVv0AAAAJ").strip()
SCHOLARLY_USE_FREE_PROXIES = os.getenv("SCHOLARLY_USE_FREE_PROXIES", "true").strip().lower() not in {"0", "false", "no"}
SCHOLARLY_PUBLICATION_LIMIT = int(os.getenv("SCHOLARLY_PUBLICATION_LIMIT", "300"))
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY")
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL")
OPENALEX_AUTHOR_ID = os.getenv("OPENALEX_AUTHOR_ID", "").strip()
DATA_PATH = Path(os.getenv("PUBLICATIONS_DIR", os.getenv("PUBLICATIONS_YAML", "data/publications")))
CITATION_META_FILE = Path(os.getenv("CITATION_META_YAML", "data/citations/meta.yaml"))
MATCH_THRESHOLD = 0.90
OPENALEX_BASE = "https://api.openalex.org"
AUTHOR_CITATION_META = {}
IGNORED_PUBLICATION_TITLE_TEXTS = [
    "Architecture designs of dendritic neuron model and swarm intelligence",
]


def normalize(text: str) -> str:
    """Return a punctuation-insensitive title key for matching.

    Google Scholar may store preprints, proceedings, and publisher records with
    slightly different punctuation, spaces, capitalization, or line wrapping.
    For matching, keep only ASCII letters and compare the compact lowercase key.
    The original title is still preserved when adding a new YAML entry.
    """
    return re.sub(r"[^a-z]+", "", str(text).lower())


IGNORED_PUBLICATION_TITLES = {normalize(title) for title in IGNORED_PUBLICATION_TITLE_TEXTS}


def quote_yaml(value) -> str:
    value = "" if value is None else str(value)
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    return raw


def field_raw_value(lines: list[str], index: int, value: str) -> str:
    """Return a scalar field value, folding YAML continuation lines if present."""
    raw = value.strip()
    if not raw:
        return raw

    parts = [] if raw in {">", ">-", ">+", "|", "|-", "|+"} else [raw]
    next_index = index + 1
    while next_index < len(lines):
        continuation = lines[next_index]
        if not continuation.strip() or continuation.lstrip().startswith("#"):
            break
        if not continuation.startswith("    "):
            break
        stripped = continuation.strip()
        if stripped.startswith("-"):
            break
        parts.append(stripped)
        next_index += 1
    return " ".join(parts) if parts else raw


def parse_entries(lines: list[str]):
    entries = []
    current = None
    for index, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            if current:
                current["end"] = index
                entries.append(current)
            current = {"key": line.rstrip()[:-1], "start": index, "fields": {}, "field_lines": {}}
            continue
        if current and re.match(r"^  [^ ].*:", line):
            name, value = line.strip().split(":", 1)
            normalized = name.lower()
            current["fields"][normalized] = parse_scalar(field_raw_value(lines, index, value))
            current["field_lines"][normalized] = index
    if current:
        current["end"] = len(lines)
        entries.append(current)
    return entries


def publication_files() -> list[Path]:
    if DATA_PATH.is_file():
        return [DATA_PATH]
    if DATA_PATH.is_dir():
        return sorted(path for path in DATA_PATH.glob("*.yaml") if path.is_file())
    return []


def read_publication_states() -> list[dict]:
    states = []
    for path in publication_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        states.append({"path": path, "lines": lines, "entries": parse_entries(lines)})
    return states


def publication_target_path(work) -> Path:
    if DATA_PATH.is_file():
        return DATA_PATH
    year = work_year(work) or "unknown"
    return DATA_PATH / f"{year}.yaml"


def publication_file_header(year: str) -> list[str]:
    return [
        f"# Publication entries for {year}.",
        "# Add one top-level entry per paper.",
        "# The site and citation updater read all YAML files in data/publications/ automatically.",
        "",
    ]


def is_hidden_entry(entry) -> bool:
    value = entry["fields"].get("display")
    return str(value).strip().lower() == "false"


def apply_line_operations(lines: list[str], operations: list[tuple[int, int, list[str]]]) -> None:
    for start, end, new_lines in sorted(operations, key=lambda item: (item[0], item[1]), reverse=True):
        lines[start:end] = new_lines


def openalex_params(extra: dict | None = None) -> str:
    params = {}
    if OPENALEX_EMAIL:
        params["mailto"] = OPENALEX_EMAIL
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    if extra:
        params.update(extra)
    return urlencode(params)


def openalex_get(path: str, params: dict | None = None):
    query = openalex_params(params)
    url = f"{OPENALEX_BASE}{path}"
    if query:
        url = f"{url}?{query}"
    request = Request(url, headers={"User-Agent": "AICLabOpenAlexCitationUpdater/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def work_title(work) -> str:
    return work.get("title") or work.get("display_name") or ""


def work_citations(work) -> int:
    try:
        return int(work.get("cited_by_count") or 0)
    except (TypeError, ValueError):
        return 0


def work_citations_by_year(work) -> dict[int, int]:
    counts = {}
    for row in work.get("counts_by_year") or []:
        try:
            year = int(row.get("year"))
            count = int(row.get("cited_by_count") or 0)
        except (TypeError, ValueError):
            continue
        counts[year] = count
    return dict(sorted(counts.items()))


def work_year(work) -> str:
    year = work.get("publication_year") or ""
    match = re.search(r"\d{4}", str(year))
    return match.group(0) if match else ""


def work_month(work) -> str:
    date = work.get("publication_date") or ""
    match = re.match(r"\d{4}-(\d{2})", str(date))
    return match.group(1) if match else ""


def work_doi(work) -> str:
    doi = work.get("doi") or ""
    return doi if doi.startswith("http") else f"https://doi.org/{doi}" if doi else ""


def work_link(work) -> str:
    doi = work_doi(work)
    if doi:
        return doi
    primary = work.get("primary_location") or {}
    landing_page = primary.get("landing_page_url") or ""
    return landing_page or work.get("id", "")


def work_source(work) -> str:
    if work.get("source"):
        return work.get("source") or ""
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    return source.get("display_name") or ""


def work_authors(work) -> str:
    if work.get("authors"):
        return work.get("authors") or ""
    names = []
    for authorship in work.get("authorships", []):
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            names.append(name)
    return ", ".join(names)


def is_ignored_title(title: str) -> bool:
    return normalize(title) in IGNORED_PUBLICATION_TITLES


def merge_duplicate_works(works: list[dict]) -> list[dict]:
    merged = {}
    order = []
    for work in works:
        title = work_title(work)
        normalized_title = normalize(title)
        if not normalized_title or normalized_title in IGNORED_PUBLICATION_TITLES:
            continue
        if normalized_title not in merged:
            merged[normalized_title] = work
            order.append(normalized_title)
            continue

        target = merged[normalized_title]
        target["cited_by_count"] = work_citations(target) + work_citations(work)

        yearly_counts = work_citations_by_year(target)
        for year, count in work_citations_by_year(work).items():
            yearly_counts[year] = yearly_counts.get(year, 0) + count
        target["counts_by_year"] = [
            {"year": year, "cited_by_count": count}
            for year, count in sorted(yearly_counts.items())
        ]

        for field in ("authors", "source", "publication_year", "publication_date", "doi", "id"):
            if not target.get(field) and work.get(field):
                target[field] = work.get(field)
    return [merged[key] for key in order]


def best_work_match(title: str, works):
    target = normalize(title)
    best = None
    best_score = 0.0
    for work in works:
        score = difflib.SequenceMatcher(None, target, normalize(work_title(work))).ratio()
        if score > best_score:
            best = work
            best_score = score
    if best_score < MATCH_THRESHOLD:
        return None, best_score
    return best, best_score


def best_entry_match(title: str, entries):
    target = normalize(title)
    best = None
    best_score = 0.0
    for entry in entries:
        candidate_title = entry["fields"].get("title", "")
        score = difflib.SequenceMatcher(None, target, normalize(candidate_title)).ratio()
        if score > best_score:
            best = entry
            best_score = score
    if best_score < MATCH_THRESHOLD:
        return None, best_score
    return best, best_score


def fetch_work_for_entry(entry):
    fields = entry["fields"]
    doi = str(fields.get("doi", "")).strip()
    if doi:
        doi_value = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
        try:
            return openalex_get(f"/works/doi:{quote(doi_value, safe='')}")
        except Exception as exc:
            print(f"[WARN] DOI lookup failed for {entry['key']}: {exc}", file=sys.stderr)

    title = str(fields.get("title", "")).strip()
    if not title:
        return None
    try:
        data = openalex_get("/works", {"search": title, "per-page": 5})
        work, _ = best_work_match(title, data.get("results", []))
        return work
    except Exception as exc:
        print(f"[WARN] title lookup failed for {entry['key']}: {exc}", file=sys.stderr)
        return None


def fetch_author_works(author_id: str):
    if not author_id:
        return []
    works = []
    cursor = "*"
    while True:
        params = {
            "filter": f"author.id:{author_id}",
            "per-page": 200,
            "cursor": cursor,
            "sort": "publication_date:desc",
        }
        data = openalex_get("/works", params)
        batch = data.get("results", [])
        works.extend(batch)
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not batch or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.1)
    return works


def scholar_import():
    try:
        from scholarly import scholarly
    except ImportError as exc:
        raise SystemExit(
            "The google_scholar citation source requires the 'scholarly' package. "
            "Install it with: pip install scholarly"
        ) from exc
    return scholarly


def scholar_year(value) -> str:
    match = re.search(r"\d{4}", str(value or ""))
    return match.group(0) if match else ""


def scholar_work_from_publication(publication: dict) -> dict:
    bib = publication.get("bib") or {}
    title = bib.get("title") or publication.get("title") or ""
    year = scholar_year(bib.get("pub_year") or bib.get("year"))
    venue = bib.get("venue") or bib.get("journal") or bib.get("conference") or ""
    authors = bib.get("author") or bib.get("authors") or ""
    citations = publication.get("num_citations")
    try:
        citations = int(citations or 0)
    except (TypeError, ValueError):
        citations = 0

    counts_by_year = []
    for year_key, count in (publication.get("cites_per_year") or {}).items():
        try:
            counts_by_year.append({"year": int(year_key), "cited_by_count": int(count or 0)})
        except (TypeError, ValueError):
            continue
    counts_by_year.sort(key=lambda row: row["year"])

    pub_url = publication.get("pub_url") or publication.get("eprint_url") or ""
    return {
        "title": title,
        "display_name": title,
        "authors": authors,
        "source": venue,
        "publication_year": year,
        "publication_date": year,
        "doi": "",
        "id": pub_url,
        "cited_by_count": citations,
        "counts_by_year": counts_by_year,
    }


def fetch_google_scholar_works(scholar_id: str) -> list[dict]:
    global AUTHOR_CITATION_META
    if not scholar_id:
        return []
    scholarly = scholar_import()
    if SCHOLARLY_USE_FREE_PROXIES:
        try:
            from fp.fp import FreeProxy

            original_get_proxy_list = FreeProxy.get_proxy_list
            if getattr(original_get_proxy_list, "__name__", "") != "get_proxy_list_compat":
                def get_proxy_list_compat(self, repeat=True):
                    return original_get_proxy_list(self, repeat)

                FreeProxy.get_proxy_list = get_proxy_list_compat
        except Exception as exc:
            print(f"[WARN] free-proxy compatibility patch skipped: {exc}", file=sys.stderr)

        from scholarly import ProxyGenerator

        proxy_generator = ProxyGenerator()
        if proxy_generator.FreeProxies():
            scholarly.use_proxy(proxy_generator, proxy_generator)
        else:
            print("[WARN] scholarly FreeProxies setup failed; trying direct Google Scholar access.", file=sys.stderr)
    author = scholarly.search_author_id(
        scholar_id,
        filled=True,
        publication_limit=SCHOLARLY_PUBLICATION_LIMIT,
    )
    AUTHOR_CITATION_META = {
        "total_citations": author.get("citedby"),
        "h_index": author.get("hindex"),
        "h_index_recent": author.get("hindex5y"),
        "i10_index": author.get("i10index"),
        "i10_index_recent": author.get("i10index5y"),
        "annual_citations": author.get("cites_per_year") or {},
    }
    works = [scholar_work_from_publication(publication) for publication in author.get("publications", [])]
    return merge_duplicate_works(works)


def make_new_key(work, existing_keys: set[str], index: int) -> str:
    year = work_year(work) or "unknown"
    base = f"new_publication_{year}_{index:02d}"
    key = base
    suffix = 2
    while key in existing_keys:
        key = f"{base}_{suffix}"
        suffix += 1
    existing_keys.add(key)
    return key


def new_publication_block(key: str, work) -> list[str]:
    source = work_source(work)
    doi = work_doi(work)
    link = "" if doi else work_link(work)
    citations_by_year = work_citations_by_year(work)
    block = [
        "",
        f"{key}:",
        f"  # TODO: Review this automatically added {source_label()} entry.",
        "  display: true",
        '  type: "preprint"',
        f"  title: {quote_yaml(work_title(work))}",
        f"  authors: {quote_yaml(work_authors(work))}",
        '  journal: ""',
        '  conference: ""',
        f"  preprint: {quote_yaml(source or source_label())}",
        f"  year: {work_year(work)}" if work_year(work) else '  year: ""',
        f"  month: {quote_yaml(work_month(work))}",
        f"  doi: {quote_yaml(doi)}",
        f"  link: {quote_yaml(link)}",
        f"  citations: {work_citations(work)}",
    ]
    if citations_by_year:
        block.append("  citations_by_year:")
        for year, count in citations_by_year.items():
            block.append(f'    "{year}": {count}')
    return block


def field_block_range(lines: list[str], entry, field_name: str):
    start = entry["field_lines"].get(field_name)
    if start is None:
        return None
    end = start + 1
    while end < entry["end"]:
        line = lines[end]
        if re.match(r"^  [^ ].*:", line) or (line.strip() and not line.startswith(" ")):
            break
        end += 1
    return start, end


def citations_by_year_block(citations_by_year: dict[int, int]) -> list[str]:
    if not citations_by_year:
        return []
    return [
        "  citations_by_year:",
        *[f'    "{year}": {count}' for year, count in citations_by_year.items()],
    ]


def insertion_index(lines: list[str]) -> int:
    index = 0
    while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith("#")):
        index += 1
    return index


def apply_citation_updates(lines: list[str], entries):
    updated = 0
    unmatched_existing = 0
    replacements = []
    insertions = []
    block_replacements = []
    matched_work_titles = set()
    matched_works = []

    for entry in entries:
        if is_hidden_entry(entry):
            continue
        work = fetch_work_for_entry(entry)
        if not work:
            unmatched_existing += 1
            continue
        matched_works.append(work)
        matched_work_titles.add(normalize(work_title(work)))
        citations = work_citations(work)
        citations_by_year = work_citations_by_year(work)
        current = entry["fields"].get("citations")
        changed = False
        if current != citations:
            if "citations" in entry["field_lines"]:
                replacements.append((entry["field_lines"]["citations"], f"  citations: {citations}"))
            else:
                insert_at = entry["end"]
                while insert_at > entry["start"] and not lines[insert_at - 1].strip():
                    insert_at -= 1
                insertions.append((insert_at, f"  citations: {citations}"))
            changed = True

        yearly_block = citations_by_year_block(citations_by_year)
        if yearly_block:
            existing_range = field_block_range(lines, entry, "citations_by_year")
            if existing_range:
                start, end = existing_range
                if lines[start:end] != yearly_block:
                    block_replacements.append((start, end, yearly_block))
                    changed = True
            else:
                insert_at = entry["field_lines"].get("citations", entry["end"]) + 1
                block_replacements.append((insert_at, insert_at, yearly_block))
                changed = True

        if changed:
            updated += 1
        time.sleep(0.1)

    operations = []
    operations.extend((start, end, new_lines) for start, end, new_lines in block_replacements)
    operations.extend((line_index, line_index + 1, [new_line]) for line_index, new_line in replacements)
    operations.extend((line_index, line_index, [new_line]) for line_index, new_line in insertions)
    apply_line_operations(lines, operations)

    return updated, unmatched_existing, matched_work_titles, matched_works


def apply_citation_updates_from_works(lines: list[str], entries, works):
    updated = 0
    unmatched_existing = 0
    replacements = []
    insertions = []
    block_replacements = []
    matched_work_titles = set()
    matched_works = []

    for entry in entries:
        if is_hidden_entry(entry):
            continue
        title = str(entry["fields"].get("title", "")).strip()
        if is_ignored_title(title):
            continue
        if not title:
            unmatched_existing += 1
            continue
        work, score = best_work_match(title, works)
        if not work:
            unmatched_existing += 1
            print(f"[WARN] no Google Scholar title match for {entry['key']}: {title} (best={score:.3f})", file=sys.stderr)
            continue

        matched_works.append(work)
        matched_work_titles.add(normalize(work_title(work)))
        citations = work_citations(work)
        citations_by_year = work_citations_by_year(work)
        current = entry["fields"].get("citations")
        changed = False

        if current != citations:
            if "citations" in entry["field_lines"]:
                replacements.append((entry["field_lines"]["citations"], f"  citations: {citations}"))
            else:
                insert_at = entry["end"]
                while insert_at > entry["start"] and not lines[insert_at - 1].strip():
                    insert_at -= 1
                insertions.append((insert_at, f"  citations: {citations}"))
            changed = True

        yearly_block = citations_by_year_block(citations_by_year)
        if yearly_block:
            existing_range = field_block_range(lines, entry, "citations_by_year")
            if existing_range:
                start, end = existing_range
                if lines[start:end] != yearly_block:
                    block_replacements.append((start, end, yearly_block))
                    changed = True
            else:
                insert_at = entry["field_lines"].get("citations", entry["end"]) + 1
                block_replacements.append((insert_at, insert_at, yearly_block))
                changed = True

        if changed:
            updated += 1

    operations = []
    operations.extend((start, end, new_lines) for start, end, new_lines in block_replacements)
    operations.extend((line_index, line_index + 1, [new_line]) for line_index, new_line in replacements)
    operations.extend((line_index, line_index, [new_line]) for line_index, new_line in insertions)
    apply_line_operations(lines, operations)

    return updated, unmatched_existing, matched_work_titles, matched_works


def prepend_missing_publications(lines: list[str], entries, works, matched_work_titles: set[str]):
    existing_keys = {entry["key"] for entry in entries}
    new_blocks = []
    new_count = 0
    for work in works:
        title = work_title(work)
        if is_ignored_title(title):
            continue
        if normalize(title) in matched_work_titles:
            continue
        entry, _ = best_entry_match(title, entries)
        if entry:
            continue
        new_count += 1
        key = make_new_key(work, existing_keys, new_count)
        new_blocks.extend(new_publication_block(key, work))

    if not new_blocks:
        return 0

    notice = [
        "",
        f"# AUTO-ADDED PUBLICATIONS FROM {source_label().upper()}",
        "# Please review these entries regularly, fill type/source/month/doi/link fields,",
        "# and rename IDs to journal_YYYY_NN, conference_YYYY_NN, or preprint_NN.",
    ]
    index = insertion_index(lines)
    lines[index:index] = notice + new_blocks + [""]
    return new_count


def prepend_missing_publications_to_files(states: list[dict], entries, works, matched_work_titles: set[str]):
    existing_keys = {entry["key"] for entry in entries}
    state_by_path = {state["path"]: state for state in states}
    new_count = 0
    added_by_path: dict[Path, list[str]] = {}

    for work in works:
        title = work_title(work)
        if is_ignored_title(title):
            continue
        if normalize(title) in matched_work_titles:
            continue
        entry, _ = best_entry_match(title, entries)
        if entry:
            continue

        new_count += 1
        key = make_new_key(work, existing_keys, new_count)
        target_path = publication_target_path(work)
        added_by_path.setdefault(target_path, []).extend(new_publication_block(key, work))

    if not added_by_path:
        return 0

    for path, new_blocks in added_by_path.items():
        if path not in state_by_path:
            year = path.stem
            path.parent.mkdir(parents=True, exist_ok=True)
            state = {"path": path, "lines": publication_file_header(year), "entries": []}
            states.append(state)
            state_by_path[path] = state
        else:
            state = state_by_path[path]

        notice = [
            "",
            f"# AUTO-ADDED PUBLICATIONS FROM {source_label().upper()}",
            "# Please review these entries regularly, fill type/source/month/doi/link fields,",
            "# and rename IDs to journal_YYYY_NN, conference_YYYY_NN, or preprint_NN.",
        ]
        index = insertion_index(state["lines"])
        state["lines"][index:index] = notice + new_blocks + [""]

    return new_count


def source_label() -> str:
    if CITATION_SOURCE in {"google_scholar", "scholar", "scholarly"}:
        return "Google Scholar"
    return "OpenAlex"


def write_citation_meta() -> None:
    updated_at = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M (JST)")
    CITATION_META_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f'source: "{source_label()}"',
        f'updated_at: "{updated_at}"',
    ]
    for key in ("total_citations", "h_index", "h_index_recent", "i10_index", "i10_index_recent"):
        value = AUTHOR_CITATION_META.get(key)
        if value is not None and value != "":
            lines.append(f"{key}: {int(value)}")
    annual = AUTHOR_CITATION_META.get("annual_citations") or {}
    if annual:
        lines.append("annual_citations:")
        for year, count in sorted(annual.items()):
            lines.append(f'  "{int(year)}": {int(count)}')
    CITATION_META_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    if not DATA_PATH.exists():
        print(f"Missing publications path: {DATA_PATH}", file=sys.stderr)
        return 1

    states = read_publication_states()
    if not states:
        print(f"No publication YAML files found in: {DATA_PATH}", file=sys.stderr)
        return 1
    entries = [entry for state in states for entry in state["entries"]]

    if CITATION_SOURCE in {"google_scholar", "scholar", "scholarly"}:
        author_id = GOOGLE_SCHOLAR_ID
        author_works = fetch_google_scholar_works(author_id)
        updated = 0
        unmatched_existing = 0
        matched_work_titles = set()
        matched_works = []
        for state in states:
            state_updated, state_unmatched, state_matched_titles, state_matched_works = apply_citation_updates_from_works(
                state["lines"],
                state["entries"],
                author_works,
            )
            updated += state_updated
            unmatched_existing += state_unmatched
            matched_work_titles.update(state_matched_titles)
            matched_works.extend(state_matched_works)
    elif CITATION_SOURCE == "openalex":
        updated = 0
        unmatched_existing = 0
        matched_work_titles = set()
        matched_works = []
        for state in states:
            state_updated, state_unmatched, state_matched_titles, state_matched_works = apply_citation_updates(
                state["lines"],
                state["entries"],
            )
            updated += state_updated
            unmatched_existing += state_unmatched
            matched_work_titles.update(state_matched_titles)
            matched_works.extend(state_matched_works)
        author_id = OPENALEX_AUTHOR_ID
        author_works = fetch_author_works(author_id) if author_id else []
    else:
        print(f"Unsupported CITATION_SOURCE: {CITATION_SOURCE}", file=sys.stderr)
        return 1

    entries_after_update = [
        entry
        for state in states
        for entry in parse_entries(state["lines"])
    ]
    added = prepend_missing_publications_to_files(states, entries_after_update, author_works, matched_work_titles)

    write_citation_meta()

    if updated or added:
        for state in states:
            state["path"].parent.mkdir(parents=True, exist_ok=True)
            state["path"].write_text("\n".join(state["lines"]).rstrip() + "\n", encoding="utf-8")
    print(
        f"{source_label()} works="
        f"{len(author_works)} entries={len(entries)} citations_updated={updated} "
        f"existing_unmatched={unmatched_existing} author_id={author_id or 'none'} "
        f"new_entries_added={added}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



