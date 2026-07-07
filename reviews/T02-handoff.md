# T02 Handoff

## Summary

- Added `src/recording.py` for timestamped output paths, transcript writing, Twilio recording polling, and dual-channel MP3 download.
- Updated `call_bridge.py` to keep the same live console utterances while also appending timestamped transcript lines for the post-call writer.
- Updated `run_call.py` to write `calls/transcripts/call_<scenario_id>_<YYYYMMDD-HHMMSS>.txt` and download `calls/recordings/call_<scenario_id>_<YYYYMMDD-HHMMSS>.mp3` after hangup.
- Updated README with the generated output file locations.

## Verification

- `env PYTHONPYCACHEPREFIX=/private/tmp/pgai-voice-tester-pyc .venv/bin/python -m compileall src`
- `.venv/bin/python -m src.run_call scenarios/01_simple_scheduling.yaml` exits before Twilio with `Missing required environment variable: OPENAI_API_KEY` when `.env` is not configured.
- Fake-client checks verified:
  - transcript basename/path format and `[MM:SS] SPEAKER: ...` formatting
  - bridge utterance logging appends transcript lines
  - recording poll waits for `completed`
  - MP3 download URL includes `RequestedChannels=2`
  - hard dial guard and dual-channel call recording settings still hold

## Open Questions

None.

## Notes

- I did not place a live call, so the acceptance condition that the MP3 has both voices still needs one configured run.
- Unrelated local changes under `docs/ARCHITECTURE.md`, `memory/`, and additional `scenarios/*.yaml` were left unstaged and are not part of this ticket.
