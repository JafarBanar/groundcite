"""cite-guard: verify in code that an LLM answer cites only the sources it was given.

The model is asked to cite. That is a request. ``cite_guard`` re-checks the answer
in plain Python after the model has spoken: every citation must resolve to a
source that was actually supplied, and (optionally) every factual sentence must
carry one. If the check fails, the caller refuses instead of returning the text.

Typical use in a retrieval-augmented pipeline::

    from cite_guard import validate, NUMERIC

    report = validate(answer_text, sources=[1, 2, 3, 4, 5], pattern=NUMERIC)
    if not report.ok:
        return "I could not answer that from the documentation."
"""

from .core import (
    CitationPattern,
    Report,
    check_quotes,
    extract_citations,
    factual_sentences,
    guard,
    validate,
)
from .patterns import BRACKET_ID, NUMERIC, SOURCE_N, THREEGPP, custom

__version__ = "0.1.0"

__all__ = [
    "BRACKET_ID",
    "NUMERIC",
    "SOURCE_N",
    "THREEGPP",
    "CitationPattern",
    "Report",
    "check_quotes",
    "custom",
    "extract_citations",
    "factual_sentences",
    "guard",
    "validate",
    "__version__",
]
