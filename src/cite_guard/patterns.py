"""Citation patterns: how a citation looks inside the answer text.

Each pattern is a compiled regular expression with a named group ``ref``. The
text captured by ``ref`` is normalised with ``normalise`` and compared with the
identifiers of the sources that were supplied to the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Pattern


@dataclass(frozen=True)
class CitationPattern:
    """A citation syntax.

    Attributes:
        name: Short label used in reports and on the command line.
        regex: Compiled pattern with a named group ``ref``.
        normalise: Maps the captured ``ref`` text to the canonical identifier
            that source ids are compared against.
    """

    name: str
    regex: Pattern[str]
    normalise: Callable[[str], str]

    def find(self, text: str) -> list[str]:
        """Return every normalised, de-duplicated ref found in ``text``, in order."""
        seen: list[str] = []
        for match in self.regex.finditer(text):
            ref = self.normalise(match.group("ref"))
            if ref not in seen:
                seen.append(ref)
        return seen


def _strip(value: str) -> str:
    return value.strip()


#: ``[3]``, ``[3, 5]``, ``[3][5]`` — plain numeric citations. Refs are the digits.
NUMERIC = CitationPattern(
    name="numeric",
    regex=re.compile(r"\[(?P<ref>\d{1,4})(?=[\],])"),
    normalise=_strip,
)

#: ``[Source 3]``, ``(Source 3)``, ``Source 3`` — the style most RAG prompts ask for.
SOURCE_N = CitationPattern(
    name="source-n",
    regex=re.compile(r"\bsource\s*(?P<ref>\d{1,4})\b", re.IGNORECASE),
    normalise=_strip,
)

#: ``[doc-12]``, ``[SB-2231]``, ``[manual_fh16_ch4]`` — any bracketed identifier
#: made of letters, digits, dots, dashes and underscores. Compared case-insensitively.
BRACKET_ID = CitationPattern(
    name="bracket-id",
    regex=re.compile(r"\[(?P<ref>[A-Za-z][A-Za-z0-9._\-:/]{0,63})\]"),
    normalise=lambda v: v.strip().lower(),
)

#: ``TS 38.331 §5.3.5.3``, ``TS 38.331 clause 5.3.5.3`` — 3GPP specification clauses.
THREEGPP = CitationPattern(
    name="3gpp",
    regex=re.compile(
        r"TS\s*(?P<ref>\d{2}\.\d{3}\s*(?:§|section\s+|clause\s+)\s*\d+(?:\.\d+)*[a-zA-Z]?)",
        re.IGNORECASE,
    ),
    normalise=lambda v: "TS " + re.sub(
        r"\s*(?:§|section\s+|clause\s+)\s*",
        " §",
        re.sub(r"^\s*TS\s*", "", v.strip(), flags=re.IGNORECASE),
        flags=re.IGNORECASE,
    ),
)


def custom(regex: str, name: str = "custom", *, ignore_case: bool = False) -> CitationPattern:
    """Build a pattern from a regular expression that has a named group ``ref``.

    Args:
        regex: Pattern source; must contain ``(?P<ref>...)``.
        name: Label for reports.
        ignore_case: Compile with ``re.IGNORECASE``.

    Raises:
        ValueError: If the expression has no ``ref`` group.
    """
    compiled = re.compile(regex, re.IGNORECASE if ignore_case else 0)
    if "ref" not in compiled.groupindex:
        raise ValueError("custom citation regex must define a named group 'ref'")
    return CitationPattern(name=name, regex=compiled, normalise=_strip)


PRESETS: dict[str, CitationPattern] = {
    p.name: p for p in (NUMERIC, SOURCE_N, BRACKET_ID, THREEGPP)
}
