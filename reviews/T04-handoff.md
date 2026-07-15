# T04 Handoff

## Summary

- Added `python -m src.run_batch scenarios/` to run validated scenarios sequentially.
- Enforced a 30-second minimum gap between completed calls; the CLI can only increase it.
- Each completed call is analyzed and added to `calls/index.md` with scenario, duration,
  recording/transcript links, and bug count.
- Added `--dry-run` to validate scenario order and pacing without loading credentials or
  constructing any Twilio call.
- Updated the single-call runner to return exact call artifacts and elapsed duration to the
  batch runner without changing the guarded call-creation site.
- Documented batch usage and the operator-attended live-session gate in README.

## Verification

- `env PYTHONPYCACHEPREFIX=/private/tmp/pgai-voice-tester-pyc .venv/bin/python -m compileall -q src tests`
- `.venv/bin/python -m unittest discover -s tests -v` (4 passing tests)
- `.venv/bin/python -m src.run_batch scenarios/ --dry-run` (14 scenarios validated in order)
- `.venv/bin/python -m src.run_batch scenarios/ --dry-run --gap-seconds 45`
- `.venv/bin/python -m src.run_batch scenarios/ --dry-run --gap-seconds 29` (correctly refused)
- Safety audit confirmed the sole `twilio_client.calls.create` remains in `run_call.py`,
  guarded by the hardcoded `+18054398008` constant.

## Open Questions

None.

## Notes

- Zero live calls were placed during T04 development or verification.
- The live batch remains deferred to the operator-attended session, after at least three clean
  single calls placed in that same sitting.
- `ruff` is not installed in the project environment; no dependency was added for it.
