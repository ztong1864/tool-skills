"""Shared term extraction for Worker ranking and experience recall."""
from __future__ import annotations

import re


# Function words carry no task meaning; counting them made every goal "match".
STOPWORDS = frozenset({
    "a", "about", "all", "an", "and", "any", "are", "as", "at", "be", "by", "can", "could",
    "do", "does", "for", "from", "have", "how", "i", "if", "in", "into", "is", "it", "its",
    "me", "my", "need", "of", "on", "or", "our", "please", "should", "so", "that", "the",
    "then", "there", "this", "to", "us", "want", "we", "what", "when", "which", "will",
    "with", "would", "you", "your",
})


def search_terms(value: str) -> set[str]:
    """Return meaningful English terms and overlapping Chinese terms."""
    terms = {term for term in re.findall(r"[a-z0-9]+", value.lower())
             if len(term) > 1 and term not in STOPWORDS}
    for run in re.findall(r"[一-鿿]+", value):
        terms.add(run)
        terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return terms
