# AGENTS.md — Operating Instructions for the Coding Agent

You are the implementer on a two-agent team. Claude (via the human) is the architect
and reviewer. You write code; Claude reviews every ticket before it is considered done.

## Project

An automated "patient" voice bot that places real phone calls to a healthcare AI agent
at +1-805-439-8008 (the ONLY number this system may ever dial — hardcode a guard),
holds a natural 1–3 minute conversation driven by a scenario file, records both sides,
transcribes the call, and flags quality bugs in the callee agent's behavior.

This is a ~500-line test harness judged on **how natural the calls sound**, not on
architecture. It will be graded by humans listening to the audio first.

## Stack (do not substitute without a ticket saying so)

- Python 3.11+, single package under `src/`
- OpenAI Realtime API (speech-to-speech) as the patient brain + voice
- Twilio Programmable Voice + Media Streams for outbound calls
- FastAPI + uvicorn for the single WebSocket endpoint Twilio connects to
- ngrok (or user-provided public URL) for the webhook tunnel
- Twilio dual-channel call recording; download to `calls/recordings/` as MP3
- Transcripts written to `calls/transcripts/` as plain text with speaker labels
  and elapsed-time stamps (e.g. `[01:23] AGENT: ...`)

## Hard constraints

1. **Never dial any number other than +1-805-439-8008.** Assert this in code at the
   single call-creation site. Refuse env overrides of the target number.
2. Audio to/from Twilio Media Streams is 8kHz G.711 mu-law. Configure the Realtime
   session for `g711_ulaw` in and out — no resampling layers.
3. Support barge-in: Realtime server VAD enabled; on `input_audio_buffer.speech_started`,
   send Twilio a `clear` event to drop buffered bot audio.
4. Secrets only via `.env` (python-dotenv). Never commit secrets. Keep `.env.example` current.
5. One command to run a call after setup: `python -m src.run_call scenarios/<file>.yaml`

## Style rules (these override your defaults)

- NO Clean Architecture layering, NO repositories/interfaces/DI containers, NO Redis,
  NO database, NO auth middleware, NO rate limiting, NO docker-compose. The graders
  explicitly penalize over-engineering.
- Small flat modules: `run_call.py`, `call_bridge.py`, `scenario.py`, `recording.py`,
  `analyze.py`. Plain functions and small classes. Type hints. Docstring per module.
- Fail loudly with actionable messages (missing env var → say which one).
- No placeholder/stub code paths. If something can't work yet, stop and write a question.

## Workflow

1. Work one ticket at a time from `tickets/`, lowest number first, on branch `ticket/T0X`.
2. When done: commit, push, and append a short summary + any open questions to
   `reviews/T0X-handoff.md`. Do not start the next ticket until the human says
   Claude approved the previous one.
3. If a ticket is ambiguous or blocked, write the question in `reviews/QUESTIONS.md`
   and stop. Do not guess on telephony/audio-format decisions.
4. Never edit files under `scenarios/` or `docs/SPEC.md` — those are Claude's.

## Definition of done for any ticket

- Runs from a fresh clone with only `.env` filled in
- No dead code, no TODOs left behind
- README updated if setup steps changed
