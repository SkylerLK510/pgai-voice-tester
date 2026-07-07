# T01 Handoff

## Summary

- Added `src/scenario.py` with Pydantic validation for Claude-owned scenario YAML and patient prompt construction.
- Added `src/call_bridge.py` with the Twilio Media Streams to OpenAI Realtime bridge: G.711 mu-law in/out, server VAD, live utterance logs, Twilio `clear` on barge-in, and graceful goodbye/hangup paths.
- Added `src/run_call.py` with `.env` loading, FastAPI/uvicorn startup, guarded outbound Twilio call creation, and dual-channel recording enabled for the later recording ticket.
- Added `pydantic` to `requirements.txt`.

## Verification

- `env PYTHONPYCACHEPREFIX=/private/tmp/pgai-voice-tester-pyc .venv/bin/python -m compileall src`
- `.venv/bin/python -m src.run_call scenarios/01_simple_scheduling.yaml` exits before Twilio with `Missing required environment variable: OPENAI_API_KEY` when `.env` is not configured.
- Fake-client checks verified:
  - hard guard rejects any target other than `+18054398008` before Twilio is called
  - valid call creation uses `to=+18054398008`, dual-channel recording, and `<Connect><Stream>`
  - Realtime session config uses `g711_ulaw` input/output and `server_vad`
  - barge-in sends Twilio `clear` and OpenAI `response.cancel`

## Open Questions

None.

## Review Fixes

- Switched the Realtime session update to the GA shape for `gpt-realtime-2.1`: `session.type`, `output_modalities`, nested `audio.input` / `audio.output`, and `audio/pcmu` G.711 mu-law formats.
- Removed the unconditional first `response.create`; server VAD now answers after the callee greeting, with a 5-second silent-callee fallback.
- Fixed the reproduced goodbye stall by retrying one canceled/no-audio goodbye response, then finishing and hanging up regardless.
- The bridge now attempts REST hangup in `finally` whenever a `call_sid` exists and the call has not already been hung up.
- `run_call` now reports outer `asyncio.TimeoutError` cleanly instead of surfacing a traceback.

## Blocked Verification

- Direct Realtime API smoke test was not run because this workspace has no `.env` and no `OPENAI_API_KEY` in the shell environment.

## Notes

- I did not place a live call.
- Unrelated local changes were already present under `docs/ARCHITECTURE.md` and additional `scenarios/*.yaml`; they were left unstaged and are not part of this ticket.
