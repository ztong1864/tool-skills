"""PrimeKG indication-only inference delivery package."""

from .inference import (
    IndicationInferenceBundle,
    ResolvedDisease,
    load_bundle,
    resolve_disease,
    score_all_candidates,
)
from .model import TorchPrimeKGIndicationRanker

__all__ = [
    "IndicationInferenceBundle",
    "ResolvedDisease",
    "TorchPrimeKGIndicationRanker",
    "load_bundle",
    "resolve_disease",
    "score_all_candidates",
]

__version__ = "0.1.0"
