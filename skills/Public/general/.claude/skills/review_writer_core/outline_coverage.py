"""Cross-check that every literature-matrix paper survives into the selected outline.

A matrix paper that never appears in any section's ``Assigned papers:`` line is
either an accidental drop or a deliberate exclusion the human reviewer must
record with a reason -- never a silent, unexplained loss. This module is the
single source of truth for that diff; both ``project_status.py`` (reporting)
and ``init_section_blueprint.py`` (a hard gate) call it fresh rather than
trusting a cached flag, so neither can be fooled by a stale confirmation.
"""

from __future__ import annotations

import re
from typing import Any


ASSIGNED_PAPERS_RE = re.compile(r"(?im)^\s*assigned papers:\s*(.+)$")
PAPER_ID_RE = re.compile(r"\b[A-Za-z]+\d+\b")


def matrix_paper_ids(matrix: Any) -> list[str]:
    """Return every paper_id present in a literature_matrix.json payload."""

    if isinstance(matrix, dict):
        rows = matrix.get("papers") if isinstance(matrix.get("papers"), list) else matrix.get("rows")
    elif isinstance(matrix, list):
        rows = matrix
    else:
        rows = None
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            paper_id = row.get("paper_id")
            if isinstance(paper_id, str) and paper_id.strip():
                ids.append(paper_id.strip())
    return ids


def outline_assigned_paper_ids(outline_text: str) -> list[str]:
    """Return the union of paper_ids across every "Assigned papers:" line.

    Deliberately not section-scoped: SKILL.md documents a plain ``## Section
    title`` heading as valid, while some consumers require a leading number
    (``1.``/``2)``). A per-line union across the whole document is immune to
    that heading-format mismatch.
    """

    ids: list[str] = []
    seen: set[str] = set()
    for match in ASSIGNED_PAPERS_RE.finditer(outline_text or ""):
        for paper_id in PAPER_ID_RE.findall(match.group(1)):
            if paper_id not in seen:
                seen.add(paper_id)
                ids.append(paper_id)
    return ids


def valid_excluded_paper_ids(excluded_papers: Any) -> list[str]:
    """Return only paper_ids carrying a genuine, non-empty exclusion reason."""

    ids: list[str] = []
    if not isinstance(excluded_papers, list):
        return ids
    for entry in excluded_papers:
        if not isinstance(entry, dict):
            continue
        paper_id = entry.get("paper_id")
        reason = entry.get("reason")
        if (
            isinstance(paper_id, str) and paper_id.strip()
            and isinstance(reason, str) and reason.strip()
        ):
            ids.append(paper_id.strip())
    return ids


def missing_outline_papers(
    matrix_ids: list[str], outline_ids: list[str], excluded_ids: list[str]
) -> list[str]:
    """Matrix papers accounted for neither in the outline nor a valid exclusion."""

    accounted = set(outline_ids) | set(excluded_ids)
    seen: set[str] = set()
    missing: list[str] = []
    for paper_id in matrix_ids:
        if paper_id not in accounted and paper_id not in seen:
            seen.add(paper_id)
            missing.append(paper_id)
    return missing


def outline_coverage_report(
    matrix: Any, outline_text: str, excluded_papers: Any = None
) -> dict[str, Any]:
    """Compose the full coverage report shared by every caller of this module."""

    matrix_ids = matrix_paper_ids(matrix)
    outline_ids = outline_assigned_paper_ids(outline_text)
    excluded_ids = valid_excluded_paper_ids(excluded_papers)
    missing = missing_outline_papers(matrix_ids, outline_ids, excluded_ids)
    return {
        "matrix_paper_ids": matrix_ids,
        "outline_paper_ids": outline_ids,
        "excluded_paper_ids": excluded_ids,
        "missing_paper_ids": missing,
    }
