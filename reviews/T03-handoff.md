# T03 Handoff

## Summary

- Added `src/analyze.py` with `python -m src.analyze <transcript>` and `python -m src.analyze --all`.
- The analyzer sends transcripts to the OpenAI Responses API with a strict JSON Schema for bug candidates.
- JSON output is written to `calls/analysis/`.
- Human-readable entries marked `UNREVIEWED` are appended to `docs/BUG_REPORT.md`.
- README now includes analyzer usage.

## Verification

- `env PYTHONPYCACHEPREFIX=/private/tmp/pgai-voice-tester-pyc .venv/bin/python -m compileall src`
- Fake OpenAI Responses API check verified:
  - request uses `/v1/responses` shape with `instructions`, `input`, `store=False`, and `text.format` JSON Schema
  - model JSON is validated into bug candidates
  - JSON analysis output is written
  - markdown report entries are appended with `UNREVIEWED`
- Local parser/path checks verified:
  - `<transcript>` and `--all` are mutually exclusive
  - empty transcripts fail loudly
  - `--all` reports no transcript files when `calls/transcripts/` has none
  - missing `OPENAI_API_KEY` fails loudly

## Open Questions

None.

## Notes

- I did not run a live LLM analysis because this workspace has no `.env` / `OPENAI_API_KEY` and no T02 transcript file.
- Unrelated local changes under `docs/ARCHITECTURE.md`, `memory/`, and additional `scenarios/*.yaml` were left unstaged and are not part of this ticket.
