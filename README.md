# cite-guard

Verify in code that an LLM answer cites only the sources it was actually given.

Asking a model to cite its sources is a request. Checking it in Python is a guarantee.
`cite-guard` runs after the model has spoken: it extracts every citation from the answer,
checks that each one resolves to a source you supplied, measures how many factual
sentences carry a citation, and optionally verifies quoted spans against the source text.
If anything fails, you refuse instead of returning the answer.

Zero dependencies. Python 3.9+.

```bash
pip install cite-guard
```

## Why

A retrieval-augmented system gives the model five passages and asks it to cite them.
The model can still write `[7]`. It can cite `[3]` for a sentence that `[3]` does not
support. It can add a sentence from memory with no citation at all. None of that
looks like an error. A confident answer with a wrong citation survives review and is
only caught when someone opens the document.

`cite-guard` makes the failure visible and lets the pipeline say no.

## Use

```python
from cite_guard import validate, guard, NUMERIC

sources = [1, 2, 3, 4, 5]          # the ids of the passages you put in the prompt
answer = model(prompt_with_passages)

report = validate(answer, sources, pattern=NUMERIC)
if not report.ok:
    print(report.problems)
    # ['citations not in the supplied sources: 7',
    #  '1 of 4 factual sentences carry no citation (coverage 0.75 < 1.00)']
```

Or the one-liner for a pipeline step:

```python
text, report = guard(answer, sources, refusal="I could not answer that from the documentation.")
return text
```

### Citation styles

| Pattern | Matches | Source ids look like |
|---|---|---|
| `NUMERIC` (default) | `[3]`, `[3, 5]`, `[3][5]` | `3` or `"3"` |
| `SOURCE_N` | `[Source 3]`, `(source 3)` | `3` |
| `BRACKET_ID` | `[SB-2231]`, `[manual_ch4]` | `"sb-2231"` (case-insensitive) |
| `THREEGPP` | `TS 38.331 §5.3.5.3`, `TS 38.331 clause 5.3.5.3` | `"TS 38.331 §5.3.5.3"` |
| `custom(r"...(?P<ref>...)...")` | anything | whatever `ref` captures |

### Quote check

If your prompt asks the model to return a short supporting quote per citation, verify
the quotes really occur in the source (case and whitespace insensitive):

```python
report = validate(
    answer, sources,
    quotes={2: ["520 Nm using a calibrated wrench"]},
    source_texts={1: passage_1, 2: passage_2, ...},
)
```

### Coverage

By default every factual sentence must carry a citation (`min_coverage=1.0`). Headings,
tables, code blocks and short organising lines like "There are three cases:" are not
counted. Loosen with `min_coverage=0.8`, or check resolution only with
`min_coverage=0.0`.

### Command line, for CI

```bash
cite-guard check answer.md --sources 1 2 3 4 5
# OK  citations=3 resolved=3 coverage=1.00 (4/4)

cite-guard check answer.md --sources 1 2 3 --pattern bracket-id --json
# exit code 1 when the check fails
```

Run your evaluation set offline, save the answers, and fail the build if any answer
cites something it was not given.

## What it does not do

It does not judge whether a cited source actually supports the sentence. That needs a
model or a human. `cite-guard` guarantees the cheaper, sharper property: nothing is
cited that was not supplied, and nothing is stated without a citation. In practice
that removes the most damaging failure, the fabricated reference.

## The report

```python
Report(
    ok=False,
    pattern="numeric",
    cited_refs=["2", "3", "7"],
    resolved_refs=["2", "3"],
    unresolved_refs=["7"],
    sentence_count=4,
    cited_sentence_count=3,
    coverage=0.75,
    uncited_sentences=["The bolt is made of hardened steel."],
    missing_quotes=[],
    problems=[...],
)
```

`report.to_dict()` is JSON-serialisable.

## Origin

Extracted from [spec-assistant-3gpp](https://github.com/JafarBanar/spec-assistant-3gpp),
a citation-grounded assistant over 3GPP specifications where a wrong clause number is
worse than no answer.

## License

MIT
