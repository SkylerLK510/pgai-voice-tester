# T04 — Batch runner + call index

- `python -m src.run_batch scenarios/` runs all scenarios sequentially with a
  configurable gap between calls (default at least 30s; never back-to-back).
- Generate calls/index.md: table of scenario, duration, recording link,
  transcript link, bug count.

Sequencing (clarified 2026-07-15): implementation and dry-run verification can
start now. NO live calls during development — verify with dry runs only, and
the target number stays a guarded constant (do not add any test-dial path).
Executing the batch against the real number happens only in the
operator-attended session, after ≥3 clean single calls placed in that same
session.

Out of scope: dashboards, parallel calls.
