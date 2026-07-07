# T01 — Outbound call bridged to OpenAI Realtime (CORE)

Build `src/run_call.py`, `src/call_bridge.py`, `src/scenario.py` per docs/SPEC.md.

Acceptance:
- `python -m src.run_call scenarios/01_simple_scheduling.yaml` places a real call
  to +1-805-439-8008 and holds a two-way conversation driven by the persona prompt.
- Server VAD turn-taking works; barge-in clears Twilio's audio buffer.
- Console logs each utterance live with speaker + elapsed time.
- Hard guard: any target number != +18054398008 raises before Twilio is called.
- Call ends gracefully at goal completion or max_seconds with a spoken goodbye.

Out of scope: recording download (T02), analysis (T03), batch runs (T04).
