"""The check itself: extract citations, resolve them, measure sentence coverage."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping, Optional, Union

from .patterns import NUMERIC, CitationPattern

SourceId = Union[str, int]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WS_RE = re.compile(r"\s+")


@dataclass
class Report:
    """Outcome of :func:`validate`.

    ``ok`` is True only when every citation resolves, coverage is not below the
    required minimum, and (when quotes were given) every quote is found in its
    source.
    """

    ok: bool
    pattern: str
    cited_refs: list[str] = field(default_factory=list)
    resolved_refs: list[str] = field(default_factory=list)
    unresolved_refs: list[str] = field(default_factory=list)
    sentence_count: int = 0
    cited_sentence_count: int = 0
    coverage: float = 0.0
    uncited_sentences: list[str] = field(default_factory=list)
    missing_quotes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Plain-dict form, safe to ``json.dumps``."""
        return asdict(self)


def _canonical(value: SourceId, pattern: CitationPattern) -> str:
    return pattern.normalise(str(value))


def extract_citations(text: str, pattern: CitationPattern = NUMERIC) -> list[str]:
    """Return the distinct citation refs in ``text``, normalised, in order of appearance."""
    return pattern.find(text)


def factual_sentences(markdown: str, min_words: int = 4) -> list[str]:
    """Split answer Markdown into sentences that ought to carry a citation.

    Headings, table rows, fenced code, horizontal rules and short organising
    fragments ("There are three cases:") are excluded so the coverage check
    measures claims, not scaffolding.
    """
    sentences: list[str] = []
    in_code = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        if line.startswith("#") or line.startswith("|") or set(line) <= set("-|:*_ "):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            candidate = sentence.strip()
            if len(candidate.split()) < min_words:
                continue
            if candidate.endswith(":"):
                continue
            sentences.append(candidate)
    return sentences


def check_quotes(
    quotes: Mapping[SourceId, Iterable[str]],
    source_texts: Mapping[SourceId, str],
    pattern: CitationPattern = NUMERIC,
) -> list[str]:
    """Return every quote that does not occur in its claimed source.

    Comparison ignores case and collapses whitespace. A quote whose source id is
    unknown is reported as missing.

    Args:
        quotes: ``{source_id: [quote, ...]}`` as produced by the model.
        source_texts: ``{source_id: full text}`` for the sources supplied.
        pattern: Used only to normalise ids the same way as citations.
    """
    norm_texts = {
        _canonical(k, pattern): _WS_RE.sub(" ", v).lower() for k, v in source_texts.items()
    }
    missing: list[str] = []
    for source_id, items in quotes.items():
        key = _canonical(source_id, pattern)
        body = norm_texts.get(key)
        for quote in items:
            needle = _WS_RE.sub(" ", quote).strip().lower()
            if not needle or body is None or needle not in body:
                missing.append(f"{key}: {quote}")
    return missing


def validate(
    text: str,
    sources: Iterable[SourceId],
    pattern: CitationPattern = NUMERIC,
    *,
    min_coverage: float = 1.0,
    min_words: int = 4,
    require_any_citation: bool = True,
    quotes: Optional[Mapping[SourceId, Iterable[str]]] = None,
    source_texts: Optional[Mapping[SourceId, str]] = None,
) -> Report:
    """Check that ``text`` cites only ``sources`` and that its claims are cited.

    Args:
        text: The model's answer (plain text or Markdown).
        sources: Identifiers of the sources that were actually supplied to the
            model, e.g. ``[1, 2, 3]`` or ``["SB-2231", "manual-ch4"]``.
        pattern: How citations look in ``text``; see :mod:`cite_guard.patterns`.
        min_coverage: Required share of factual sentences that carry a citation,
            0.0 to 1.0. Use ``0.0`` to check resolution only.
        min_words: Sentences shorter than this are not counted as factual.
        require_any_citation: Fail a non-empty answer that cites nothing.
        quotes: Optional ``{source_id: [quote, ...]}`` to verify verbatim spans.
        source_texts: Full texts for the quote check, keyed like ``sources``.

    Returns:
        A :class:`Report`; ``report.ok`` is the verdict.
    """
    available = {_canonical(s, pattern) for s in sources}
    problems: list[str] = []

    cited = extract_citations(text, pattern)
    resolved = [r for r in cited if r in available]
    unresolved = [r for r in cited if r not in available]

    sentences = factual_sentences(text, min_words=min_words)
    uncited = [s for s in sentences if not pattern.regex.search(s)]
    cited_count = len(sentences) - len(uncited)
    coverage = cited_count / len(sentences) if sentences else 1.0

    if unresolved:
        problems.append("citations not in the supplied sources: " + ", ".join(unresolved))
    if require_any_citation and text.strip() and not cited:
        problems.append("the answer cites no source at all")
    if sentences and coverage < min_coverage:
        problems.append(
            f"{len(uncited)} of {len(sentences)} factual sentences carry no citation "
            f"(coverage {coverage:.2f} < {min_coverage:.2f})"
        )

    missing_quotes: list[str] = []
    if quotes is not None:
        if source_texts is None:
            raise ValueError("source_texts is required when quotes are given")
        missing_quotes = check_quotes(quotes, source_texts, pattern)
        if missing_quotes:
            problems.append(f"{len(missing_quotes)} quote(s) not found in their source")

    return Report(
        ok=not problems,
        pattern=pattern.name,
        cited_refs=cited,
        resolved_refs=resolved,
        unresolved_refs=unresolved,
        sentence_count=len(sentences),
        cited_sentence_count=cited_count,
        coverage=round(coverage, 4),
        uncited_sentences=uncited,
        missing_quotes=missing_quotes,
        problems=problems,
    )


def guard(
    text: str,
    sources: Iterable[SourceId],
    pattern: CitationPattern = NUMERIC,
    *,
    refusal: str = "I could not answer that from the supplied sources.",
    **kwargs,
) -> tuple[str, Report]:
    """Return ``text`` if it passes :func:`validate`, else ``refusal``.

    A convenience for the common pipeline step: generate, check, return or refuse.
    Extra keyword arguments are passed to :func:`validate`.
    """
    report = validate(text, sources, pattern, **kwargs)
    return (text if report.ok else refusal), report
