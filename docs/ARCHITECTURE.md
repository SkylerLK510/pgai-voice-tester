# Architecture

The harness is a patient simulator that phones the practice's AI agent and hunts
for bugs. `run_call.py` loads a YAML scenario (persona, goal, steering rules,
success criteria — schema-validated with Pydantic), then uses Twilio's REST API
to place an outbound call to the target number with dual-channel recording
enabled. The call's TwiML connects a bidirectional Media Stream to our FastAPI
WebSocket server, where `call_bridge.py` — the only latency-critical file —
splices Twilio's 8kHz G.711 mu-law audio directly into an OpenAI Realtime API
session configured for the same codec. Speech-to-speech means no STT→LLM→TTS
cascade to stream-optimize: server VAD handles turn-taking, and when the callee
starts speaking over queued audio we clear Twilio's buffer and cancel the
in-flight response, so the simulated patient interrupts and gets interrupted
like a real one. Transcripts with wall-clock offsets are captured live; calls
end on goal completion or a scenario timeout with a natural spoken goodbye.

Everything after hangup is deliberately offline: `recording.py` downloads the
dual-channel MP3, and `analyze.py` runs the transcript through an LLM QA rubric
to produce structured bug candidates, which a human curates into
`docs/BUG_REPORT.md`. The design is intentionally small — a single-operator
local harness, not a service — so there are no auth layers, session stores, or
API versioning; effort went into what's audible (codec fidelity, sub-800ms
turn latency, barge-in, graceful timeout fallbacks) and what's safe (secrets
only in `.env`, and the target phone number hardcoded as a constant behind a
guard at the single call-creation site, so the harness cannot dial anyone else).
