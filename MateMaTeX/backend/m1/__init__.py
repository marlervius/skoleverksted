"""M1 — empirisk verifikasjonsdekning (MateMaTeX grunnlov §1, milepæl M1)."""

from m1.scorer import VERIFIED, MISMATCH, UNCERTAIN, aggregate, answer_check, report

__all__ = [
    "VERIFIED",
    "MISMATCH",
    "UNCERTAIN",
    "answer_check",
    "aggregate",
    "report",
]
