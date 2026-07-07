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

## Notes

- I did not place a live call.
- Unrelated local changes were already present under `docs/ARCHITECTURE.md` and additional `scenarios/*.yaml`; they were left unstaged and are not part of this ticket.
