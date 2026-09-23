#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _review_runtime.paths import (
    resolve_mineru_output_root,
    resolve_pdf_root,
    resolve_review_root,
    resolve_review_writer_core_root,
)

_CORE_ROOT = resolve_review_writer_core_root(anchor=Path(__file__))
if _CORE_ROOT is not None and str(_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_ROOT))

from review_writer_core.taxonomy import (  # noqa: E402
    labels_by_category,
    load_rules_from_path,
    load_taxonomy_rules,
    resolve_taxonomy_path,
    suggest_taxonomy_profile,
    taxonomy_identity,
)


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

MARKDOWN_FRONT_MATTER_CHARS = 30_000

# Excludes DOI matches that only appear inside a References/Bibliography
# section so a paper's own DOI is not shadowed by a DOI belonging to a work
# it cites. Upstream review-writer's publication_metadata.py has the same
# gaps this closes: it only recognized a bare "References"/"Bibliography"
# heading with nothing else on the line, missing both "Notes and references"
# and ACS's own "## ■ REFERENCES" (a decorative bullet MinerU preserves
# literally between the markdown "##" and the heading word) -- hence the
# `[^\w\s]{0,3}\s*` gap below, tolerant of a few decorative symbol characters.
#
# Deliberately does NOT also cut at Acknowledgements/Funding/Data
# Availability, even though those sections can carry a stray funder/dataset
# DOI (see the 10.13039/ funder-registry guard below instead): tried that
# first, and it regressed two ACS-published papers whose own self-referential
# "Supporting Information is available ... at pubs.acs.org/doi/<self-DOI>"
# sentence sits *after* their Data Availability Statement, so cutting there
# discarded the paper's only real DOI candidate. Section order near the end
# of a paper varies enough by publisher that heading-based cutoff is unsafe
# for anything less unambiguous than References/Bibliography itself.
REFERENCES_HEADING_RE = re.compile(
    r"(?im)^\s*#{0,6}\s*[^\w\s]{0,3}\s*(?:(?:notes\s+and\s+)?references|reference\s+list|bibliography|works\s+cited|参考文献|引用文献)\s*$"
)
# A run of several numbered citation-shaped lines (e.g. "[12] A. Author, ...",
# "(12) A. Author, ...", or "12. A. Author, ...") reliably marks the start of
# a reference list even when MinerU dropped its heading entirely -- seen in
# practice both for a paper whose reference list begins right after "Data
# Availability Statement" with no "References" line at all, and for ACS-style
# "(1) Author, A. Title. Journal Year, ..." parenthesized numbering, which is
# equally common and easy to miss if only "[N]" is matched. Matches a
# numbered-citation line followed by two more within a short distance, so a
# single incidental "[3]"-style inline citation in body text doesn't trigger it.
_REF_NUM = r"(?:\(\d{1,3}\)|\[\d{1,3}\]|\d{1,3}[.)])"
REFERENCE_LIST_RUN_RE = re.compile(
    r"(?:^|\n)" + _REF_NUM + r"\s+[A-Z][^\n]{0,40}(?:,|\.\s)[^\n]{0,300}"
    r"(?:\n{1,3}" + _REF_NUM + r"\s+[A-Z][^\n]{0,40}(?:,|\.\s)){2,}"
)
# Only excludes a *bare* DOI-shaped number found near one of these words --
# e.g. a library "Downloaded on <date>" stamp. Even then, an explicitly
# self-labeled match ("DOI: ..." / "doi.org/...") in the first ~3000 chars
# (title/author/abstract block, before any body or reference text) is never
# excluded by this: real papers overwhelmingly print "Received: X, Revised:
# Y, Accepted: Z, DOI: 10.xxx" as one front-matter line, so penalizing
# "accepted" here would strike the paper's own DOI specifically because it
# sits next to its own accept date. The position cutoff matters: a *late*
# explicit match can legitimately be a reference-list citation (e.g. "...
# Elsevier, 2017, 269-286. DOI: 10.1016/B978-...") that this same carve-out
# would otherwise wrongly protect.
EXCLUDED_DOI_CONTEXT_RE = re.compile(
    r"\b(?:received|revised|accepted|downloaded|accessed|retrieved|created|modified|uploaded|scanned)\b",
    re.I,
)
DOI_FRONT_MATTER_HEADER_CHARS = 3000
# The Crossref Funder Registry prefix (funding-body identifiers, e.g. NSF,
# Beckman Foundation) is never a real article DOI. Seen in practice: a paper
# whose Acknowledgements cited a fellowship as "(dx.doi.org/10.13039/...)",
# which otherwise outscored the paper's own DOI because nothing else in
# front matter was DOI-shaped enough to compete with an explicit label.
FUNDER_REGISTRY_DOI_PREFIX = "10.13039/"

JOURNAL_HINTS = [
    "Angewandte Chemie International Edition",
    "Angew. Chem. Int. Ed.",
    "Advanced Synthesis & Catalysis",
    "Adv. Synth. Catal.",
    "Tetrahedron Letters",
    "Tetrahedron",
    "European Journal of Organic Chemistry",
    "Eur. J. Org. Chem.",
    "Organic Letters",
    "Journal of Organic Chemistry",
    "Chemical Communications",
    "Green Chemistry",
    "Chemical Science",
]

STRUCTURED_TAG_KEYS = [
    "product",
    "substrate",
    "catalyst_or_method",
    "organometallic_partner",
    "ligand_or_chiral_source",
    "leaving_group",
    "reaction_type",
    "document_scope",
]

DEFAULT_CLASSIFICATION_LABELS = {key: ["not specified"] for key in STRUCTURED_TAG_KEYS}

CHEM_TAG_RULES = {
    "propargylic alcohols": ["propargylic alcohol", "propargylic alcohols"],
    "propargylic derivatives": ["propargylic derivative", "propargylic derivatives", "propargyl"],
    "allenes": ["allene", "allenes", "allenamide", "allenamides"],
    "substituted allenes": ["substituted allene", "multisubstituted allene", "disubstituted allene"],
    "copper catalysis": ["copper", "cui", "cu(", "copper-catalyzed"],
    "nickel catalysis": ["nickel", "ni(", "nickel-catalyzed"],
    "palladium catalysis": ["palladium", "pd(", "palladium-catalyzed"],
    "gold catalysis": ["gold", "au(", "gold-catalyzed"],
    "rhodium catalysis": ["rhodium", "rh(", "rhodium-catalyzed"],
    "photoredox catalysis": ["photoredox", "visible-light", "light-mediated"],
    "enantioselective synthesis": ["enantioselective", "enantiospecific", "enantioenriched", "ee"],
    "cross-electrophile coupling": ["cross-electrophile"],
    "radical reaction": ["radical", "radicals"],
    "carbonylation": ["carbonylation"],
    "C-H activation": ["c-h activation", "ch activation"],
    "SN2' substitution": ["sn2", "substitution", "displacement"],
    "mechanism": ["mechanism", "catalytic cycle", "intermediate", "control experiment", "dft"],
    "total synthesis": ["total synthesis", "natural product"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" .", ".").replace(" ,", ",").strip()
    return text


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_classification_rules(path: Path) -> dict[str, list[str]]:
    return labels_by_category(load_rules_from_path(path), STRUCTURED_TAG_KEYS)


def sample_topic_text(meta_dir: Path, *, limit: int = 8) -> str:
    """Build a representative topic string from existing papers' title/abstract
    so resolve_classification_labels can auto-detect a real taxonomy profile
    instead of always falling back to the empty general_academic default."""
    parts: list[str] = []
    for path in sorted(meta_dir.glob("*.metadata.json"))[:limit]:
        try:
            meta = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        title = (meta.get("title") or {}).get("value") or ""
        abstract = (meta.get("abstract") or {}).get("value") or ""
        if title:
            parts.append(str(title))
        if abstract:
            parts.append(str(abstract)[:500])
    return " ".join(parts)


def resolve_classification_labels(review_root: Path, topic_text: str = "") -> dict[str, list[str]]:
    """Auto-detect a real taxonomy profile from paper content (title/abstract)
    instead of always falling back to the empty general_academic default,
    which produces "not specified" for every structured tag regardless of
    what the papers are actually about (see suggest_taxonomy_profile)."""
    profile = suggest_taxonomy_profile(topic_text) if topic_text.strip() else ""
    rules = load_taxonomy_rules(review_root, profile=profile, topic_text=topic_text)
    return labels_by_category(rules, STRUCTURED_TAG_KEYS)


def classification_rules_prompt(labels: dict[str, list[str]]) -> str:
    lines = [
        "Allowed classification labels for this review's active taxonomy. For each category, output exactly one label from its list.",
        "Use `not specified` only when no listed label is supported by the supplied paper evidence.",
    ]
    for key in STRUCTURED_TAG_KEYS:
        lines.append(f"\n{key}:")
        for label in labels.get(key, ["not specified"]):
            lines.append(f"- {label}")
    return "\n".join(lines)


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "paper"


def scored(value: Any, source: str, confidence: float) -> dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "confidence": round(float(confidence), 3),
        "human_checked": False,
    }


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def iter_jobs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for job in manifest.get("completed", []):
        if isinstance(job, dict):
            jobs.append(job)
    if jobs:
        return jobs
    for batch in manifest.get("batches", []):
        for job in batch.get("jobs", []):
            if isinstance(job, dict) and job.get("state") == "done":
                jobs.append(job)
    return jobs


def jobs_from_pdf_root(pdf_root: Path, mineru_output: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for index, pdf_path in enumerate(sorted(pdf_root.rglob("*.pdf")), start=1):
        relative_stem = str(pdf_path.relative_to(pdf_root).with_suffix(""))
        # MinerU parser versions before the Windows path-length fix emitted the
        # full slug; newer runs shorten it with a deterministic hash. Accept
        # both layouts so an incremental library can be rebuilt completely.
        legacy_slug = slugify_mineru(relative_stem, shorten=False)
        base_slug = slugify_mineru(relative_stem)
        seen[base_slug] = seen.get(base_slug, 0) + 1
        slug = base_slug if seen[base_slug] == 1 else f"{base_slug}-{seen[base_slug]:02d}"
        candidates = [slug]
        if legacy_slug != slug:
            candidates.append(legacy_slug)
        resolved_slug = next(
            (
                candidate
                for candidate in candidates
                if (mineru_output / "markdown" / f"{candidate}.md").exists()
                or (mineru_output / "extracted" / candidate / "full.md").exists()
            ),
            None,
        )
        if resolved_slug is None:
            continue
        slug = resolved_slug
        extracted_dir = mineru_output / "extracted" / slug
        markdown_copy = mineru_output / "markdown" / f"{slug}.md"
        full_md = extracted_dir / "full.md"
        jobs.append(
            {
                "pdf_name": pdf_path.name,
                "relative_pdf_path": str(pdf_path.relative_to(pdf_root)),
                "slug": slug,
                "data_id": f"{index:03d}-{slug}"[:96],
                "state": "done",
                "err_msg": "",
                "raw_zip": str(mineru_output / "raw_zips" / f"{slug}.zip"),
                "extracted_dir": str(extracted_dir),
                "full_md": str(full_md),
                "markdown_copy": str(markdown_copy),
            }
        )
    return jobs


def slugify_mineru(value: str, shorten: bool = True) -> str:
    import hashlib
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9._/-]+", "-", ascii_text).strip("-._/")
    cleaned = cleaned.replace("/", "__")
    cleaned = re.sub(r"-{2,}", "-", cleaned).lower() or "document"
    if shorten and len(cleaned) > 72:
        cleaned = f"{cleaned[:55].rstrip('-')}-{hashlib.sha1(cleaned.encode()).hexdigest()[:12]}"
    return cleaned


def read_registry_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def max_paper_number(rows: list[dict[str, Any]]) -> int:
    max_number = 0
    for row in rows:
        paper_id = str(row.get("paper_id") or "")
        match = re.fullmatch(r"P(\d+)", paper_id)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return max_number


def registry_key(row: dict[str, Any]) -> str:
    return str(row.get("source_pdf") or row.get("markdown_path") or row.get("slug") or row.get("paper_id") or "")


def content_list_path(extracted_dir: Path) -> Path | None:
    candidates = sorted(extracted_dir.glob("*_content_list.json"))
    if not candidates:
        candidates = sorted(extracted_dir.rglob("*_content_list.json"))
    return candidates[0] if candidates else None


def load_blocks(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    data = read_json(path)
    return data if isinstance(data, list) else []


def block_texts(blocks: list[dict[str, Any]], max_page: int = 1) -> list[str]:
    out: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("page_idx", 999) > max_page:
            continue
        if block.get("type") not in {"text", "list", "table", "image", "chart"}:
            continue
        text = block.get("text") or block.get("content") or ""
        captions = block.get("image_caption") or []
        if isinstance(captions, list):
            text = " ".join([text] + [str(c) for c in captions])
        text = clean_text(str(text))
        if text:
            out.append(text)
    return out


def markdown_head(path: Path | None, chars: int = MARKDOWN_FRONT_MATTER_CHARS) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")[:chars]


# Conservative title recovery, ported from upstream review-writer's
# review_writer_core/document_front_matter.py. MinerU sometimes uses an
# extraction folder name such as ``p001`` as the document title while the
# real article title remains an H1-H3 Markdown heading; these helpers inspect
# only the bounded front matter and reject common section/boilerplate
# headings and placeholder slugs before accepting a heading as the title.
_MARKDOWN_HEADING_RE = re.compile(r"(?m)^\s{0,3}(#{1,3})\s+(.+?)\s*$")
_PLACEHOLDER_TITLE_RE = re.compile(
    r"^(?:"
    r"p(?:age)?[-_ ]?\d{1,6}|part[-_ ]?\d{1,6}|"
    r"document[-_ ]?\d*|article[-_ ]?\d*|main(?:\s+document)?|"
    r"full[-_ ]?text|untitled(?:\s+document)?"
    r")$",
    re.I,
)
_BOILERPLATE_TITLE_HEADINGS = (
    re.compile(r"^(?:working\s+with\s+)?hazardous\s+chemicals?$", re.I),
    re.compile(r"^(?:general\s+)?(?:experimental\s+)?procedures?$", re.I),
    re.compile(r"^(?:abstract|summary|keywords?|introduction|background)$", re.I),
    re.compile(r"^(?:results?(?:\s+and\s+discussion)?|discussion|conclusions?)$", re.I),
    re.compile(r"^(?:notes?|references?|bibliography|supporting\s+information)$", re.I),
    re.compile(r"^(?:article\s+info(?:rmation)?|graphical\s+abstract)$", re.I),
)


def clean_markdown_heading(value: Any) -> str:
    """Return visible heading text without Markdown/HTML presentation residue."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    text = re.sub(r"(?:\\[A-Za-z]+|[†‡*]+|<sup>.*?</sup>)", " ", text, flags=re.I)
    text = text.replace("­", "")
    # PDF text layers often split chemical names with typographic hyphens
    # (for example ``2,3-‐butadien-‐1-‐ol``). Canonicalize them before title
    # validation.
    text = re.sub(r"[-‐‑‒–—﹘﹣－]+", "-", text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n#|_")
    return text


def looks_like_placeholder_title(value: Any) -> bool:
    """Identify extraction slugs and generic PDF titles, including ``p001``."""
    title = clean_markdown_heading(value)
    if not title:
        return True
    if _PLACEHOLDER_TITLE_RE.fullmatch(title):
        return True
    lowered = title.casefold()
    return lowered.startswith("doi:") or lowered in {
        "microsoft word",
        "main document",
        "article",
    }


def _title_heading_allowed(value: str) -> bool:
    if not 8 <= len(value) <= 320 or looks_like_placeholder_title(value):
        return False
    compact = re.sub(r"[\s:.-]+", " ", value).strip()
    if any(pattern.fullmatch(compact) for pattern in _BOILERPLATE_TITLE_HEADINGS):
        return False
    if re.fullmatch(r"(?:volume|vol|issue|page|chapter)\s+\w+", compact, re.I):
        return False
    if re.fullmatch(r"[\W\d_]+", compact):
        return False
    return True


def extract_markdown_title(markdown: Any, *, limit: int = MARKDOWN_FRONT_MATTER_CHARS) -> dict[str, Any] | None:
    """Recover the first credible H1-H3 title from bounded MinerU Markdown."""
    front = str(markdown or "")[: max(1, int(limit))]
    for match in _MARKDOWN_HEADING_RE.finditer(front):
        value = clean_markdown_heading(match.group(2))
        if not _title_heading_allowed(value):
            continue
        level = len(match.group(1))
        confidence = {1: 0.9, 2: 0.86, 3: 0.8}[level]
        return {
            "value": value,
            "source": f"mineru_markdown_h{level}_front_matter",
            "confidence": confidence,
            "human_checked": False,
        }
    return None


def extract_title(blocks: list[dict[str, Any]], md: str, slug: str) -> dict[str, Any]:
    heading = extract_markdown_title(md)
    if heading is not None:
        return heading
    for block in blocks[:12]:
        text = clean_text(str(block.get("text") or ""))
        if (
            block.get("text_level") == 1
            and len(text) > 8
            and not looks_like_section_heading(text)
            and not looks_like_placeholder_title(text)
        ):
            return scored(text, "content_list_text_level_1", 0.86)
    return scored(slug.replace("-", " "), "slug_fallback", 0.35)


def looks_like_section_heading(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).lower()
    return compact in {
        "abstract",
        "articleinfo",
        "keywords",
        "introduction",
        "references",
        "conclusion",
        "conclusions",
    }


def extract_authors(blocks: list[dict[str, Any]], title_value: str) -> dict[str, Any]:
    title_seen = False
    candidates: list[str] = []
    for block in blocks[:20]:
        text = clean_text(str(block.get("text") or ""))
        if not text:
            continue
        if clean_text(title_value)[:35] in text or text[:35] in clean_text(title_value):
            title_seen = True
            continue
        if title_seen:
            if text.lower().startswith("abstract:") or len(text) > 260:
                break
            if re.search(r"\b(college|university|institute|laboratory|department|school|china|usa|abstract|keywords|herein|given the)\b", text, re.I):
                break
            if "," in text or re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+", text):
                candidates.append(text)
    if not candidates:
        return scored([], "rule_not_found", 0.0)
    raw = " ".join(candidates)
    raw = re.sub(r"\\\*|\*|\ba,b\b|\ba\b|\bb\b|\bc\b|\d+|†|‡", "", raw)
    parts = [clean_text(p) for p in re.split(r"\s*,\s*|\s+ and \s+", raw) if clean_text(p)]
    authors = []
    for part in parts:
        part = re.sub(r"\s+[a-z](?:\s+[a-z])?$", "", part).strip()
        part = re.sub(r"\\$", "", part).strip()
        part = part.replace("\\", "")
        part = re.sub(r"^and\s+", "", part, flags=re.I).strip()
        if 3 <= len(part) <= 80 and not re.search(r"\b(college|university|laboratory|key)\b", part, re.I):
            authors.append(part)
    authors = dedupe(authors)
    return scored(authors, "content_list_after_title", 0.74 if authors else 0.0)


def extract_keywords(blocks: list[dict[str, Any]], md: str) -> dict[str, Any]:
    texts = block_texts(blocks, max_page=1)
    keywords: list[str] = []
    for i, text in enumerate(texts[:60]):
        compact = re.sub(r"\s+", "", text).lower()
        if compact in {"keywords:", "keywords"}:
            for nxt in texts[i + 1 : i + 10]:
                if looks_like_section_heading(nxt) or re.search(r"\babstract\b", nxt, re.I):
                    break
                if 2 <= len(nxt) <= 90:
                    keywords.append(nxt.strip(" ;,."))
            break
    if not keywords:
        m = re.search(r"Keywords:\s*(.+?)(?:\n\s*#|\n\s*A\s*B\s*S\s*T\s*R\s*A\s*C\s*T)", md, re.I | re.S)
        if m:
            raw = m.group(1)
            keywords = [clean_text(x).strip(" ;,.") for x in re.split(r"\n|;|,", raw) if clean_text(x)]
    keywords = [kw for kw in dedupe(keywords) if 2 <= len(kw) <= 80]
    return scored(keywords[:12], "content_list_keywords_region", 0.86 if keywords else 0.0)


def extract_abstract(blocks: list[dict[str, Any]], md: str) -> dict[str, Any]:
    texts = block_texts(blocks, max_page=2)
    for i, text in enumerate(texts[:80]):
        compact = re.sub(r"\s+", "", text).lower()
        if compact in {"abstract", "abstract:"} or compact == "abstract":
            parts: list[str] = []
            for nxt in texts[i + 1 : i + 35]:
                if re.match(r"^\d+\.\s+[A-Z]", nxt) or re.search(r"\bintroduction\b", nxt, re.I):
                    break
                if len(nxt) > 30:
                    parts.append(nxt)
            abstract = clean_text(" ".join(parts))
            if len(abstract) > 150:
                return scored(abstract, "content_list_abstract_region", 0.84)
        if text.lower().startswith("abstract:"):
            abstract = clean_text(text.split(":", 1)[1])
            if len(abstract) > 150:
                return scored(abstract, "content_list_inline_abstract", 0.84)
    m = re.search(r"#\s*A\s*B\s*S\s*T\s*R\s*A\s*C\s*T\s*(.+?)(?:\n#\s*\d+\.|\n#\s*1\.|\n#\s*Introduction)", md, re.I | re.S)
    if m:
        abstract = clean_text(re.sub(r"\n+", " ", m.group(1)))
        if len(abstract) > 80:
            return scored(abstract, "markdown_abstract_heading", 0.82)
    m = re.search(r"\bAbstract:\s*(.+?)(?:\n\s*#\s*Introduction|\n\s*#|\n\n#)", md, re.I | re.S)
    if m:
        abstract = clean_text(re.sub(r"\n+", " ", m.group(1)))
        if len(abstract) > 80:
            return scored(abstract, "markdown_inline_abstract", 0.82)
    intro = extract_intro_work_summary(md)
    if intro:
        return scored(intro, "markdown_introduction_ending_summary", 0.72)
    title_idx = None
    author_idx = None
    affiliation_like_re = re.compile(
        r"\b("
        r"university|institute|laboratory|lab\b|department|school|academy|"
        r"state key laboratory|academy of sciences|college|hospital|center|centre|"
        r"road|street|avenue|lu\b|china|usa|p\.?\s*r\.?\s*china|"
        r"shanghai|beijing|dalian|guangzhou|nanjing|wuhan|chengdu"
        r")\b",
        re.I,
    )
    abstract_signal_re = re.compile(
        r"\b("
        r"herein|we report|we describe|we disclose|we present|we developed|we have developed|"
        r"we demonstrate|we herein report|this paper|this work|this study|"
        r"a method|an efficient method|a practical method|protocol|procedure|"
        r"approach|strategy|transformation|construction|formation|access to|"
        r"is described|is reported|is disclosed|has been developed|has been achieved|"
        r"provides|enable(?:s|d)?|furnish(?:es|ed)?|deliver(?:s|ed)?|using|via|"
        r"enantioselective|asymmetric|selective|stereoselective|regioselective|chemoselective|"
        r"cataly[sz]ed|synthesis|prepared|afforded|reaction|under mild conditions|"
        r"in good yields|with high ee|with excellent"
        r")\b",
        re.I,
    )
    for i, block in enumerate(blocks[:20]):
        text = clean_text(str(block.get("text") or ""))
        if block.get("text_level") == 1 and len(text) > 20 and not looks_like_section_heading(text):
            title_idx = i
            continue
        if title_idx is not None and author_idx is None and 5 <= len(text) <= 260:
            if re.search(r"\b[A-Z][a-z]+", text) and ("," in text or " and " in text):
                author_idx = i
                continue
        if author_idx is not None and i > author_idx:
            if block.get("type") == "text" and 100 <= len(text) <= 1600:
                if not re.search(r"\b(introduction|keywords|received|accepted|cite this)\b", text[:80], re.I):
                    if affiliation_like_re.search(text):
                        continue
                    if not abstract_signal_re.search(text):
                        continue
                    return scored(text, "content_list_first_paragraph_after_authors", 0.68)
    return scored("", "rule_not_found", 0.0)


def extract_intro_work_summary(md: str) -> str:
    intro_match = re.search(
        r"\n#\s*(?:\d+\.?\s*)?Introduction\s*(.+?)(?:\n#\s*(?:\d+\.?\s*)?[A-Z])",
        md,
        re.I | re.S,
    )
    if not intro_match:
        return ""
    intro = intro_match.group(1)
    intro = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", intro)
    intro = re.sub(r"\$([^$]+)\$", r"\1", intro)
    intro = clean_text(intro)
    if len(intro) < 200:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", intro)
    sentences = [clean_text(s) for s in sentences if clean_text(s)]
    if len(sentences) < 2:
        return ""
    tail = sentences[-5:]
    signal_re = re.compile(
        r"\b("
        r"herein|in this work|in this paper|in this study|we report|we describe|we disclose|"
        r"we present|we developed|we have developed|we demonstrate|to address this|"
        r"based on this|using this|this work|this paper"
        r")\b",
        re.I,
    )
    selected = [s for s in tail if signal_re.search(s)]
    if not selected:
        return ""
    summary = clean_text(" ".join(selected[-3:]))
    return summary if len(summary) > 120 else ""


def extract_year(md: str, pdf_name: str) -> dict[str, Any]:
    candidates = [int(m.group(0)) for m in YEAR_RE.finditer(pdf_name + "\n" + md[:8000])]
    candidates = [y for y in candidates if 1800 <= y <= 2035]
    if candidates:
        # Prefer recent years in filename/front matter.
        return scored(max(set(candidates), key=candidates.count), "filename_or_front_matter", 0.68)
    return scored(None, "rule_not_found", 0.0)


def front_matter_text(text: str, *, limit: int = MARKDOWN_FRONT_MATTER_CHARS) -> str:
    """Return article front matter without letting a References section (or
    Acknowledgements/Funding/Data Availability, which sit between the body
    and References and commonly carry their own DOI-shaped grant or dataset
    identifiers) in.

    Originally ported from upstream review-writer's publication_metadata.py;
    that heading-only approach missed both non-standard heading text (e.g.
    "Notes and references") and references lists MinerU parsed with no
    heading line at all, so REFERENCE_LIST_RUN_RE now catches the latter by
    its numbered-citation shape instead of relying solely on a heading.
    """
    candidate = str(text or "")[: max(1, int(limit))]
    cut = len(candidate)
    heading_match = REFERENCES_HEADING_RE.search(candidate)
    if heading_match:
        cut = min(cut, heading_match.start())
    run_match = REFERENCE_LIST_RUN_RE.search(candidate)
    if run_match:
        cut = min(cut, run_match.start())
    return candidate[:cut]


def extract_doi(md: str) -> dict[str, Any]:
    front = front_matter_text(md, limit=1_000_000)
    candidates: list[tuple[int, int, str, str]] = []
    for m in DOI_RE.finditer(front):
        doi = m.group(0).rstrip(").,;").casefold()
        if doi.startswith(FUNDER_REGISTRY_DOI_PREFIX):
            continue
        context = front[max(0, m.start() - 80) : m.end() + 30]
        # "doi.org/10.xxx" is commonly printed without a URL scheme (e.g. a
        # "How to cite: ... doi.org/10.xxx" line), so this must not require
        # "https?://" to count as an explicit self-label.
        explicit = bool(re.search(r"(?:doi\.org/|\bdoi\s*:)", context, re.I))
        how_to_cite = bool(re.search(r"how\s+to\s+cite", context, re.I))
        is_header_zone = m.start() < DOI_FRONT_MATTER_HEADER_CHARS
        # A bare DOI-shaped number near "accepted"/"downloaded"/etc. is
        # probably noise (e.g. a library "Downloaded on <date>" stamp) -- but
        # papers overwhelmingly print "Received: X, Revised: Y, Accepted: Z,
        # DOI: 10.xxx" as one line, so an *explicitly* self-labeled match in
        # the header zone must never be penalized just for sitting next to
        # its own accept date. A late explicit match gets no such pass: nothing
        # but a reference-list citation is ever this far into the document.
        excluded = bool(EXCLUDED_DOI_CONTEXT_RE.search(context)) and not (explicit and is_header_zone)
        score = 3 if how_to_cite else 2 if explicit else 1
        if excluded:
            score -= 1
        candidates.append(
            (score, -m.start(), doi, "front_matter_explicit_doi" if explicit else "front_matter_doi_candidate")
        )
    if not candidates:
        return scored(None, "rule_not_found", 0.0)
    # Tuple order is (score, -position, doi, source): highest score wins,
    # ties broken toward the earliest match -- a paper's own DOI is always
    # near the top (title/author block), while a citation's DOI only ever
    # appears after the full body of the paper.
    score, _neg_pos, doi, source = max(candidates)
    return scored(doi, source, 0.78 if score >= 2 else 0.62)


def extract_journal(md: str, pdf_name: str) -> dict[str, Any]:
    hay = pdf_name + "\n" + md[:8000]
    for hint in JOURNAL_HINTS:
        if hint.lower() in hay.lower():
            return scored(hint, "known_journal_hint", 0.72)
    cite = re.search(r"Cite this:\s*([^,\n]+)", hay, re.I)
    if cite:
        return scored(clean_text(cite.group(1)), "cite_this_line", 0.7)
    how = re.search(r"How to cite:\s*([^,\n]+)", hay, re.I)
    if how:
        return scored(clean_text(how.group(1)), "how_to_cite_line", 0.7)
    filename = Path(pdf_name).stem
    if " - " in filename:
        first = filename.split(" - ")[0].strip()
        if len(first) > 3:
            return scored(first, "filename_prefix", 0.55)
    return scored(None, "rule_not_found", 0.0)


def infer_tags(text: str) -> list[str]:
    low = text.lower()
    tags: list[str] = []
    for tag, needles in CHEM_TAG_RULES.items():
        if any(n in low for n in needles):
            tags.append(tag)
    return tags


def classify_tags(tags: list[str]) -> tuple[list[str], list[str], list[str], list[str]]:
    topic = [t for t in tags if t in {"propargylic alcohols", "propargylic derivatives", "allenes", "substituted allenes"}]
    reaction = [t for t in tags if t in {"SN2' substitution", "cross-electrophile coupling", "radical reaction", "carbonylation", "C-H activation"}]
    reaction += [t for t in tags if "catalysis" in t]
    mechanism = [t for t in tags if t in {"mechanism", "radical reaction", "photoredox catalysis"}]
    application = [t for t in tags if t in {"total synthesis", "enantioselective synthesis"}]
    return dedupe(topic), dedupe(reaction), dedupe(mechanism), dedupe(application)


def dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        item = clean_text(str(item))
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def sha256_file(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_llm_payload(
    base: dict[str, Any],
    blocks: list[dict[str, Any]],
    md_head: str,
    system_prompt: str,
    model: str,
    reasoning_effort: str = "",
    classification_labels: dict[str, list[str]] | None = None,
    wire_api: str = "responses",
) -> dict[str, Any]:
    classification_labels = classification_labels or DEFAULT_CLASSIFICATION_LABELS
    front_blocks = []
    for i, block in enumerate(blocks[:80]):
        text = clean_text(str(block.get("text") or block.get("content") or ""))
        if text:
            front_blocks.append(
                {
                    "block_id": i,
                    "type": block.get("type"),
                    "text_level": block.get("text_level"),
                    "page_idx": block.get("page_idx"),
                    "text": text[:1200],
                }
            )
    user_content = {
        "path_hints": {
            "slug": base["slug"],
            "pdf": base["source_paths"]["pdf"],
            "markdown": base["source_paths"]["markdown"],
        },
        "rule_extracted_initial_metadata": {
            k: base.get(k)
            for k in [
                "title",
                "authors",
                "year",
                "journal",
                "doi",
                "abstract",
                "structured_tags",
            ]
        },
        "classification_rules": classification_rules_prompt(classification_labels),
        "front_blocks": front_blocks,
        "markdown_head": md_head[:9000],
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "title",
            "authors",
            "year",
            "journal",
            "doi",
            "abstract",
            "structured_tags",
            "warnings",
        ],
        "properties": {
            "title": field_schema("string"),
            "authors": field_schema("array"),
            "year": field_schema("integer_or_null"),
            "journal": field_schema("string_or_null"),
            "doi": field_schema("string_or_null"),
            "abstract": field_schema("string"),
            "structured_tags": structured_tags_schema(classification_labels),
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
    }
    nonce = uuid.uuid4().hex
    if wire_api == "chat-completions":
        schema_prompt = (
            f"{system_prompt}\n\nReturn only one JSON object matching this JSON Schema exactly "
            f"(no markdown fences, no explanations):\n{json.dumps(schema, ensure_ascii=False)}"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": schema_prompt},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "metadata": {"request_nonce": nonce},
        }
        # Reasoning-capable models reject a non-default temperature unless
        # reasoning_effort is "none" ("Non-default `temperature` values are
        # supported for this model only when `reasoning_effort` is `none`").
        # Only pin it for the classic, non-reasoning case; otherwise let the
        # model use its own default rather than guessing a compatible value.
        if not reasoning_effort or reasoning_effort.lower() == "none":
            # GreatRouter's reasoning-capable models reject non-default
            # temperatures; use the OpenAI-compatible default explicitly.
            payload["temperature"] = 1
        return payload
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "paper_metadata_extraction",
                "schema": schema,
                "strict": True,
            }
        },
        "prompt_cache_key": nonce,
        "metadata": {"request_nonce": nonce},
    }
    if reasoning_effort and reasoning_effort.lower() != "none":
        payload["reasoning"] = {"effort": reasoning_effort}
    return payload


def field_schema(kind: str) -> dict[str, Any]:
    if kind == "array":
        value_schema: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
    elif kind == "integer_or_null":
        value_schema = {"type": ["integer", "null"]}
    elif kind == "string_or_null":
        value_schema = {"type": ["string", "null"]}
    else:
        value_schema = {"type": "string"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["value", "source", "confidence", "human_checked"],
        "properties": {
            "value": value_schema,
            "source": {"type": "string"},
            "confidence": {"type": "number"},
            "human_checked": {"type": "boolean"},
        },
    }


def structured_tags_schema(classification_labels: dict[str, list[str]] | None = None) -> dict[str, Any]:
    classification_labels = classification_labels or DEFAULT_CLASSIFICATION_LABELS
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["value", "source", "confidence", "human_checked"],
        "properties": {
            "value": {
                "type": "object",
                "additionalProperties": False,
                "required": STRUCTURED_TAG_KEYS,
                "properties": {
                    key: {"type": "string", "enum": classification_labels.get(key, ["not specified"])}
                    for key in STRUCTURED_TAG_KEYS
                },
            },
            "source": {"type": "string"},
            "confidence": {"type": "number"},
            "human_checked": {"type": "boolean"},
        },
    }


def openai_endpoint(base_url: str, endpoint: str) -> str:
    """Accept OpenAI-compatible base URLs with or without a trailing /v1."""
    base = str(base_url or "https://api.openai.com").rstrip("/")
    prefix = "" if base.lower().endswith("/v1") else "/v1"
    return f"{base}{prefix}/{endpoint.lstrip('/')}"


def _foundryclaw_openai_config() -> dict[str, str] | None:
    """Resolve the invoking user's saved OPENAI-API-KEY provider from the
    FounDryClaw backend. Returns None (never raises) when
    FOUNDRYCLAW_MODEL_ROUTER_* is unset (e.g. standalone use outside
    FounDryClaw), the call fails, or the user hasn't saved a key -- callers
    must fall through to their normal env-var cascade in every such case.
    Shared (via import) by llm_retag_metadata.py and batch_llm_retag_metadata.py."""
    base = str(os.environ.get("FOUNDRYCLAW_MODEL_ROUTER_BASE_URL") or "").strip()
    token = str(os.environ.get("FOUNDRYCLAW_MODEL_ROUTER_TOKEN") or "").strip()
    if not base or not token:
        return None
    request = urllib.request.Request(
        base.rstrip("/") + "/api/model-router/internal/openai-key",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return None
    if not isinstance(payload, dict) or not payload.get("configured"):
        return None
    resolved = {
        "base_url": str(payload.get("base_url") or "").strip(),
        "api_key": str(payload.get("api_key") or "").strip(),
        "model": str(payload.get("model") or "").strip(),
    }
    return resolved if all(resolved.values()) else None


def resolve_api_key(cli_value: str, base_url: str) -> str:
    if cli_value:
        return cli_value
    if "api.xiaoleai.team" in str(base_url).lower():
        return os.environ.get("XIAOLEAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    return os.environ.get("OPENAI_API_KEY", "") or os.environ.get("XIAOLEAI_API_KEY", "")


TRANSIENT_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def decode_json_object(raw: bytes | str, context: str) -> dict[str, Any]:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            print(
                f"warning: {context} response was not valid UTF-8; "
                "decoding with replacement characters",
                file=sys.stderr,
            )
            text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    text = text.strip()
    if not text:
        raise RuntimeError(f"{context} returned an empty response")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        preview = re.sub(r"\s+", " ", text)[:240]
        raise RuntimeError(f"{context} returned non-JSON content: {preview}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{context} returned {type(value).__name__}; expected a JSON object")
    return value


def open_json_request(
    request: urllib.request.Request,
    *,
    timeout: int,
    context: str,
    attempts: int = 3,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=timeout) as response:
                return decode_json_object(response.read(), context)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            preview = re.sub(r"\s+", " ", detail)[:240]
            last_error = RuntimeError(
                f"{context} was rejected (HTTP {exc.code})" + (f": {preview}" if preview else "")
            )
            if exc.code not in TRANSIENT_HTTP_CODES or attempt == attempts:
                raise last_error from exc
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if attempt == attempts:
                raise RuntimeError(f"{context} failed after {attempts} attempts: {exc}") from exc
        time.sleep(min(2 ** (attempt - 1), 4))
    raise RuntimeError(f"{context} failed: {last_error}")


def call_openai_responses(
    payload: dict[str, Any], api_key: str, base_url: str = "https://api.openai.com", wire_api: str = "responses"
) -> dict[str, Any]:
    endpoint = "chat/completions" if wire_api == "chat-completions" else "responses"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        openai_endpoint(base_url, endpoint),
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "review-writer-metadata-prep/1.0",
        },
        method="POST",
    )
    data = open_json_request(req, timeout=120, context="Metadata model request")
    if wire_api == "chat-completions":
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Chat completions response did not contain choices[0].message.content") from exc
        return decode_json_object(text, "Metadata model output")
    text = data.get("output_text")
    if not text:
        parts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parts.append(content["text"])
        text = "\n".join(parts)
    if not text:
        raise RuntimeError("OpenAI response did not contain output_text")
    return decode_json_object(text, "Metadata model output")


def merge_llm(base: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "abstract",
        "structured_tags",
    ]:
        if not isinstance(llm.get(key), dict):
            continue
        current = base.get(key, {})
        if isinstance(current, dict) and current.get("human_checked"):
            continue
        new_value = llm[key].get("value")
        new_conf = float(llm[key].get("confidence") or 0)
        old_conf = float(current.get("confidence") or 0)
        current_value = current.get("value") if isinstance(current, dict) else None
        schema_changed = key == "structured_tags" and (
            not isinstance(current_value, dict) or set(current_value) != set(STRUCTURED_TAG_KEYS)
        )
        # A structured_tags dict of nothing but "not specified" placeholders
        # carries zero real information regardless of its stored confidence,
        # but has_value() sees any non-empty dict as "having a value" -- so a
        # stale run that happened to tag an empty result with high confidence
        # (e.g. the pre-taxonomy-fix runs) would otherwise permanently block
        # every future retag's genuinely informative result from ever
        # overwriting it, since new_conf >= old_conf would never hold.
        current_is_empty_tags = key == "structured_tags" and isinstance(current_value, dict) and all(
            str(v).strip().lower() == "not specified" for v in current_value.values()
        )
        if has_value(new_value) and (
            schema_changed or current_is_empty_tags or new_conf >= old_conf or not has_value(current_value)
        ):
            base[key] = {
                "value": new_value,
                "source": llm[key].get("source") or "llm",
                "confidence": round(new_conf, 3),
                "human_checked": bool(llm[key].get("human_checked", False)),
            }
    if isinstance(base.get("structured_tags"), dict):
        apply_structured_tags_to_compat_fields(base)
    warnings = llm.get("warnings") or []
    if isinstance(warnings, list):
        base["quality"]["warnings"].extend(str(w) for w in warnings if str(w).strip())
    return base


def normalize_structured_tags(value: Any) -> dict[str, str]:
    tags: dict[str, str] = {}
    if isinstance(value, dict):
        for key in STRUCTURED_TAG_KEYS:
            raw = clean_text(str(value.get(key) or "not specified"))
            tags[key] = raw or "not specified"
    else:
        tags = {key: "not specified" for key in STRUCTURED_TAG_KEYS}
    return tags


def structured_tags_from_legacy(
    topic: list[str],
    reaction: list[str],
    mechanism: list[str],
    application: list[str],
) -> dict[str, str]:
    return {
        "product": first_or_not_specified([x for x in topic if "allene" in x]),
        "substrate": first_or_not_specified([x for x in topic if "proparg" in x]),
        "catalyst_or_method": first_or_not_specified([x for x in reaction if "catalysis" in x]),
        "organometallic_partner": "not specified",
        "ligand_or_chiral_source": first_or_not_specified([x for x in application if "enantio" in x]),
        "leaving_group": "not specified",
        "reaction_type": first_or_not_specified(reaction),
        "document_scope": "primary research article",
    }


def structured_tags_from_classification_rules(review_root: Path, text: str) -> dict[str, str]:
    """Assign only labels defined by the repository's active taxonomy."""
    values = {key: "not specified" for key in STRUCTURED_TAG_KEYS}
    rules = load_taxonomy_rules(review_root)
    haystack = text.casefold()
    for item in rules:
        if not isinstance(item, tuple) or len(item) < 3:
            continue
        label, category, needles = item[0], item[1], item[2]
        if category not in values or values[category] != "not specified":
            continue
        if any(str(needle).casefold() in haystack for needle in needles if str(needle).strip()):
            values[category] = str(label)
    return values


def first_or_not_specified(items: list[str]) -> str:
    for item in items:
        item = clean_text(str(item))
        if item:
            return item
    return "not specified"


def structured_tag_values(meta: dict[str, Any]) -> dict[str, str]:
    field = meta.get("structured_tags")
    value = field.get("value") if isinstance(field, dict) else None
    return normalize_structured_tags(value)


def apply_structured_tags_to_compat_fields(meta: dict[str, Any]) -> None:
    for key in [
        "keywords",
        "llm_tags",
        "human_tags",
        "topic_category",
        "reaction_category",
        "mechanism_category",
        "application_category",
    ]:
        meta.pop(key, None)


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def update_quality(meta: dict[str, Any]) -> None:
    missing: list[str] = []
    warnings: list[str] = list(meta.get("quality", {}).get("warnings", []))
    for key in ["title", "abstract"]:
        if not has_value(meta.get(key, {}).get("value")):
            missing.append(key)
    for key in ["authors"]:
        if not has_value(meta.get(key, {}).get("value")):
            warnings.append(f"empty_{key}")
    for key in ["year"]:
        if not has_value(meta.get(key, {}).get("value")):
            missing.append(key)
    for key in ["journal", "doi"]:
        if not has_value(meta.get(key, {}).get("value")):
            warnings.append(f"missing_{key}")
    structured = structured_tag_values(meta)
    for key, value in structured.items():
        if not value or value.lower() == "not specified":
            warnings.append(f"structured_tag_not_specified_{key}")
    confidences = []
    for key in [
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "abstract",
        "structured_tags",
    ]:
        field = meta.get(key)
        if isinstance(field, dict):
            confidences.append(float(field.get("confidence") or 0))
    overall = sum(confidences) / len(confidences) if confidences else 0
    if float(meta.get("title", {}).get("confidence") or 0) < 0.75:
        warnings.append("low_confidence_title")
    if float(meta.get("abstract", {}).get("confidence") or 0) < 0.75:
        warnings.append("low_confidence_abstract")
    meta["quality"] = {
        "missing_fields": dedupe(missing),
        "warnings": dedupe(warnings),
        "overall_confidence": round(overall, 3),
        "needs_human_check": bool(missing or warnings or meta.get("human_review", {}).get("status") != "reviewed"),
    }


def existing_metadata(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = read_json(path)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def build_metadata(
    paper_id: str,
    job: dict[str, Any],
    pdf_path: Path | None,
    md_path: Path | None,
    content_path: Path | None,
    existing: dict[str, Any] | None,
    review_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], str, list[dict[str, Any]]]:
    slug = str(job.get("slug") or slugify(job.get("pdf_name") or paper_id))
    blocks = load_blocks(content_path)
    md = markdown_head(md_path)
    title = extract_title(blocks, md, slug)
    authors = extract_authors(blocks, title["value"])
    keywords = extract_keywords(blocks, md)
    abstract = extract_abstract(blocks, md)
    year = extract_year(md, job.get("pdf_name") or slug)
    doi = extract_doi(markdown_head(md_path, chars=1_000_000))
    journal = extract_journal(md, job.get("pdf_name") or slug)
    text_for_tags = " ".join(
        [
            str(title.get("value") or ""),
            str(abstract.get("value") or ""),
            " ".join(keywords.get("value") or []),
            md[:6000],
        ]
    )
    tags = infer_tags(text_for_tags)
    structured_tags = structured_tags_from_classification_rules(review_root, text_for_tags)
    pdf_hash = sha256_file(pdf_path)
    meta: dict[str, Any] = {
        "paper_id": paper_id,
        "slug": slug,
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "doi": doi,
        "abstract": abstract,
        "structured_tags": scored(structured_tags, "active_taxonomy_keyword_inference", 0.45 if tags else 0.0),
        "source_paths": {
            "pdf": str(pdf_path) if pdf_path else None,
            "markdown": str(md_path) if md_path else None,
            "content_list": str(content_path) if content_path else None,
            "extracted_dir": str(job.get("extracted_dir")) if job.get("extracted_dir") else None,
        },
        "source_file": {
            "pdf_name": job.get("pdf_name"),
            "relative_pdf_path": job.get("relative_pdf_path"),
            "sha256": pdf_hash,
        },
        "extraction": {
            "mode": "rules",
            "model": None,
            "created_at": utc_now(),
            "inputs": {
                "manifest": str(review_root / "mineru-outputs" / "manifest.json"),
                "content_blocks": len(blocks),
                "markdown_chars_used": min(len(md), MARKDOWN_FRONT_MATTER_CHARS),
                "taxonomy": taxonomy_identity(review_root),
            },
            "notes": [],
        },
        "human_review": existing.get("human_review")
        if existing and isinstance(existing.get("human_review"), dict)
        else {
            "status": "not_reviewed",
            "reviewed_at": None,
            "reviewer": None,
            "notes": [],
        },
        "quality": {
            "missing_fields": [],
            "warnings": [],
            "overall_confidence": 0,
            "needs_human_check": True,
        },
    }
    apply_structured_tags_to_compat_fields(meta)
    if existing:
        preserve_human_checked_fields(meta, existing)
    update_quality(meta)
    registry_row = {
        "paper_id": paper_id,
        "slug": slug,
        "title": meta["title"]["value"],
        "authors": meta["authors"]["value"],
        "year": meta["year"]["value"],
        "journal": meta["journal"]["value"],
        "doi": meta["doi"]["value"],
        "source_pdf": meta["source_paths"]["pdf"],
        "markdown_path": meta["source_paths"]["markdown"],
        "content_list_path": meta["source_paths"]["content_list"],
        "metadata_path": str(review_root / "review-library" / "metadata" / "papers" / f"{paper_id}.metadata.json"),
        "parse_status": "done",
        "human_review_status": meta["human_review"]["status"],
        "needs_human_check": meta["quality"]["needs_human_check"],
    }
    return meta, blocks, md, [registry_row]


def preserve_human_checked_fields(meta: dict[str, Any], existing: dict[str, Any]) -> None:
    for key, old in existing.items():
        if key in {"paper_id", "slug", "source_paths", "source_file", "extraction", "quality"}:
            continue
        if isinstance(old, dict) and old.get("human_checked") is True:
            meta[key] = old


def copy_references(skill_root: Path, review_root: Path) -> None:
    dest = review_root / "review-library" / "metadata" / "extraction_prompts"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ["metadata_extraction_system.md", "metadata_schema.json"]:
        src = skill_root / "references" / name
        if src.exists():
            (dest / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    review_root = resolve_review_root(args.review_root, anchor=Path(__file__))
    load_dotenv(review_root / ".env")
    mineru_output = resolve_mineru_output_root(args.mineru_output, review_root=review_root, anchor=Path(__file__))
    pdf_root = resolve_pdf_root(args.pdf_root, review_root=review_root, anchor=Path(__file__))
    skill_root = Path(__file__).resolve().parents[1]
    out_meta_dir = review_root / "review-library" / "metadata" / "papers"
    out_registry = review_root / "review-library" / "registry" / "papers.jsonl"
    out_meta_dir.mkdir(parents=True, exist_ok=True)
    out_registry.parent.mkdir(parents=True, exist_ok=True)
    copy_references(skill_root, review_root)
    manifest_path = mineru_output / "manifest.json"
    if args.discover_from_pdf_root:
        if not pdf_root:
            print("ERROR: --discover-from-pdf-root requires --pdf-root", file=sys.stderr)
            return 2
        jobs = jobs_from_pdf_root(pdf_root, mineru_output)
    else:
        if not manifest_path.exists():
            print(f"ERROR: missing MinerU manifest: {manifest_path}", file=sys.stderr)
            return 2
        manifest = read_json(manifest_path)
        jobs = iter_jobs(manifest)

    system_prompt = (skill_root / "references" / "metadata_extraction_system.md").read_text(encoding="utf-8")
    # An explicit --base-url/--api-key always wins, so manual debugging on the
    # box stays predictable; SKILL.md-driven runs never pass these flags.
    foundryclaw = None if (args.base_url or args.api_key) else _foundryclaw_openai_config()
    if foundryclaw:
        base_url = foundryclaw["base_url"]
        api_key = foundryclaw["api_key"]
        model = args.model or foundryclaw["model"]
    else:
        base_url = args.base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        api_key = resolve_api_key(args.api_key, base_url)
        model = args.model or os.environ.get("REVIEW_METADATA_MODEL", "gpt-5.4")
    reasoning_effort = args.reasoning_effort or os.environ.get("REVIEW_METADATA_REASONING_EFFORT", "high")
    wire_api = args.wire_api or os.environ.get("REVIEW_METADATA_WIRE_API", "responses")
    classification_labels = load_classification_rules(resolve_taxonomy_path(review_root))
    use_llm = bool(args.use_llm)
    if use_llm and not api_key:
        print("WARN: --use-llm was set but OPENAI_API_KEY is missing; using rules only.", file=sys.stderr)
        use_llm = False

    existing_rows = read_registry_rows(out_registry) if args.append_registry else []
    existing_by_key = {registry_key(row): row for row in existing_rows if registry_key(row)}
    rows: list[dict[str, Any]] = []
    next_paper_number = max_paper_number(existing_rows) + 1
    for index, job in enumerate(jobs, start=1):
        slug = str(job.get("slug") or slugify(job.get("pdf_name") or f"paper-{index:03d}"))
        md_path = Path(job["markdown_copy"]).resolve() if job.get("markdown_copy") else None
        if not md_path or not md_path.exists():
            full_md = Path(job["full_md"]).resolve() if job.get("full_md") else None
            md_path = full_md if full_md and full_md.exists() else None
        extracted_dir = Path(job["extracted_dir"]).resolve() if job.get("extracted_dir") else mineru_output / "extracted" / slug
        cpath = content_list_path(extracted_dir)
        pdf_path = None
        if pdf_root and job.get("relative_pdf_path"):
            candidate = pdf_root / str(job["relative_pdf_path"])
            if candidate.exists():
                pdf_path = candidate.resolve()
        if not pdf_path:
            origin_candidates = sorted(extracted_dir.glob("*_origin.pdf"))
            if origin_candidates:
                pdf_path = origin_candidates[0].resolve()
        candidate_key = str(pdf_path) if pdf_path else str(md_path or slug)
        existing_row = existing_by_key.get(candidate_key)
        if existing_row:
            paper_id = str(existing_row.get("paper_id"))
        else:
            paper_id = f"P{next_paper_number:03d}"
            next_paper_number += 1
        meta_path = out_meta_dir / f"{paper_id}.metadata.json"
        existing = existing_metadata(meta_path)
        meta, blocks, md, reg_rows = build_metadata(paper_id, job, pdf_path, md_path, cpath, existing, review_root)
        if use_llm:
            try:
                payload = build_llm_payload(
                    meta, blocks, md, system_prompt, model, reasoning_effort, classification_labels, wire_api
                )
                llm_data = call_openai_responses(payload, api_key or "", base_url, wire_api)
                merge_llm(meta, llm_data)
                meta["extraction"]["mode"] = "rules+llm"
                meta["extraction"]["model"] = model
                meta["extraction"]["notes"].append("llm_enhanced_metadata")
                update_quality(meta)
                if args.sleep_seconds:
                    time.sleep(args.sleep_seconds)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                meta["extraction"]["notes"].append(f"llm_failed: {type(exc).__name__}: {exc}")
                meta["quality"]["warnings"].append("llm_failed")
                update_quality(meta)
        write_json(meta_path, meta)
        reg = reg_rows[0]
        reg.update(
            {
                "title": meta["title"]["value"],
                "authors": meta["authors"]["value"],
                "year": meta["year"]["value"],
                "journal": meta["journal"]["value"],
                "doi": meta["doi"]["value"],
                "human_review_status": meta["human_review"]["status"],
                "needs_human_check": meta["quality"]["needs_human_check"],
            }
        )
        rows.append(reg)
        print(f"{paper_id} {slug} metadata written")

    if args.append_registry:
        new_keys = {registry_key(row) for row in rows if registry_key(row)}
        rows = [row for row in existing_rows if registry_key(row) not in new_keys] + rows
    tmp = out_registry.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    tmp.replace(out_registry)
    print(f"Wrote {len(rows)} papers to {out_registry}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare review paper metadata from MinerU outputs.")
    parser.add_argument("--review-root", default=None)
    parser.add_argument("--mineru-output", default=None)
    parser.add_argument("--pdf-root", default=None)
    parser.add_argument(
        "--discover-from-pdf-root",
        action="store_true",
        help="Discover parsed MinerU outputs by matching PDFs under --pdf-root to markdown/extracted outputs.",
    )
    parser.add_argument(
        "--append-registry",
        action="store_true",
        help="Append or update papers in the existing registry instead of replacing papers.jsonl.",
    )
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--reasoning-effort", default="", choices=["", "none", "low", "medium", "high"])
    parser.add_argument("--wire-api", default="", choices=["", "responses", "chat-completions"])
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    args = parser.parse_args()
    root = resolve_review_root(args.review_root, anchor=Path(__file__))
    args.mineru_output = args.mineru_output or str(root / "mineru-outputs")
    args.pdf_root = args.pdf_root or str(root / "source-paper")
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
