# T04 Review — Batch runner + call index

**Verdict: APPROVE** (with one small direct fix by reviewer, noted below)

## What was checked

1. Read the full `main...ticket/T04` diff (`src/run_batch.py`, `src/run_call.py`
   changes, tests, README).
2. Safety guard: audited every call-creation path on the branch. The sole
   `twilio_client.calls.create` remains in `run_call.py` with `to=TARGET_NUMBER`
   (the hardcoded constant), the mismatch guard intact, and env-var target
   overrides still refused. `run_batch.py` never touches Twilio — it routes
   every call through `run_call.run()`. Nothing parameterizes the number.
3. Pacing (per amended ticket): `MIN_GAP_SECONDS = 30` enforced —
   `--gap-seconds 29` is refused with a clear message, the default is 30, and
   the gap sleep sits between sequential calls (after the previous call's
   analysis, so real spacing is gap + analysis time). No parallelism anywhere.
4. Dry-run safety: ran `--dry-run` with all Twilio/OpenAI credentials stripped
   from the environment — it validates and lists all 14 scenarios in order
   without loading settings or constructing a client. Tests assert
   `load_settings` is never called in dry-run mode.
5. `run_call.py` changes preserve T02's write-transcript-in-finally behavior;
   the new `CallResult` return and no-transcript RuntimeError are sound
   (a call that produces zero transcript items fails loudly — correct, since
   the operator is present and should stop and look).
6. Compile check clean; all 4 regression tests pass. Index rendering verified:
   relative links from `calls/index.md`, mm:ss durations, bug counts.
7. Zero live calls placed during this review (dry runs only).

## Direct fix by reviewer (14 lines, `src/run_batch.py`)

As submitted, a transient analyzer failure (e.g. an OpenAI 5xx) between calls
raised out of `run()` and aborted the rest of the batch — even though the
call itself succeeded and its recording/transcript were already on disk.
During the one operator-attended session that would waste the remaining
scenarios or force re-dialing completed ones. Analysis is best-effort per
SPEC ("offline, not latency-sensitive") and `python -m src.analyze` already
exists as the backfill path, so I made `_analyze_call` catch analyzer
exceptions, print a loud WARNING with the exact backfill command, and record
the row with bug count "pending" (-1 sentinel). Verified: batch continues
through analyzer failures, all 4 existing tests still pass, index renders
"pending". Codex may add a regression test for this path in a later ticket if
desired; not required.

## Non-blocking notes (no action needed)

- If a *call* (not analysis) fails mid-batch, the batch stops — deliberate and
  correct with a human present. Completed rows survive because the index is
  rewritten after every call. Manual resume path: copy the remaining scenario
  YAMLs to a temp dir and point `run_batch` at it.
- Index duration is measured from call placement (includes ring time). Fine
  for a navigation artifact.
- A YAML *syntax* error in a scenario file would surface as a traceback rather
  than a clean one-liner (`yaml.YAMLError` isn't in main's catch tuple).
  Scenarios are schema-validated and already all load, so not worth a round.

Merged to main. Live batch execution remains gated on the operator-attended
session, after ≥3 clean single calls in that same sitting, per the ticket.
