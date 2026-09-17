"""Command line: ``groundcite check answer.md --sources 1 2 3`` exits 1 on failure.

Meant for CI gates and evaluation scripts: run the model offline, save answers,
check them here, fail the build if any answer cites a source it was not given.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import validate
from .patterns import PRESETS, custom


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="groundcite", description=__doc__)
    parser.add_argument("--version", action="version", version=f"groundcite {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="validate one answer file")
    check.add_argument("answer", type=Path, help="file with the model's answer")
    check.add_argument("--sources", nargs="+", required=True, metavar="ID",
                       help="ids of the sources that were supplied to the model")
    check.add_argument("--pattern", default="numeric",
                       help="preset name (" + ", ".join(PRESETS) + ") or a regex with a (?P<ref>...) group")
    check.add_argument("--min-coverage", type=float, default=1.0,
                       help="required share of factual sentences with a citation (default 1.0)")
    check.add_argument("--allow-uncited", action="store_true",
                       help="do not fail an answer that cites nothing at all")
    check.add_argument("--json", action="store_true", help="print the full report as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    pattern = PRESETS.get(args.pattern) or custom(args.pattern)
    text = args.answer.read_text(encoding="utf-8")
    report = validate(
        text,
        args.sources,
        pattern,
        min_coverage=args.min_coverage,
        require_any_citation=not args.allow_uncited,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        status = "OK" if report.ok else "FAIL"
        print(f"{status}  citations={len(report.cited_refs)} resolved={len(report.resolved_refs)} "
              f"coverage={report.coverage:.2f} ({report.cited_sentence_count}/{report.sentence_count})")
        for problem in report.problems:
            print(f"  - {problem}")
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
