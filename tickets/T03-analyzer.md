# T03 — Post-call bug analyzer

`src/analyze.py`: takes a transcript path (or --all), sends it to an LLM with the
QA rubric below, outputs bug candidates as JSON to calls/analysis/ and appends
human-readable entries to docs/BUG_REPORT.md (marked "UNREVIEWED").

Rubric dimensions: identity verification, factual consistency within the call,
invalid date/time acceptance (e.g. weekend appointments), hallucinated policies,
failure to answer the actual question, loops/repetition, mishandled interruptions,
inappropriate handling of ambiguity, call-flow dead ends.

Each bug: severity (high/med/low), transcript file + timestamp, expected vs actual,
one-line reproduction hint.

Acceptance: running it on the T02 transcript produces sane, non-nitpick candidates.
