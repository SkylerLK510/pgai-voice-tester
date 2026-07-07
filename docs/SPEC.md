# System Spec — Patient Simulator & Bug Finder

## Data flow

```
run_call.py <scenario.yaml>
   │ 1. load scenario → build patient persona system prompt
   │ 2. start FastAPI ws server (if not running) + resolve PUBLIC_BASE_URL
   │ 3. Twilio REST: create outbound call to +1-805-439-8008
   │      with dual-channel recording enabled,
   │      TwiML <Connect><Stream url="wss://.../media-stream">
   ▼
call_bridge.py   (the only latency-critical file)
   Twilio Media Stream (8kHz mu-law, base64 frames)
        ⇄ OpenAI Realtime API session (g711_ulaw in/out, server VAD,
          persona prompt, temperature ~0.8)
   - forward inbound audio → input_audio_buffer.append
   - forward response.audio.delta → Twilio media frames
   - on speech_started while bot audio queued → Twilio "clear" (barge-in)
   - capture conversation item transcripts with wall-clock offsets
   - scenario timeout (default 240s) or goal-completion → patient says a natural
     goodbye, wait for audio to flush, hang up via Twilio REST
   ▼
recording.py: poll recording status → download dual-channel MP3 →
   calls/recordings/call_<scenario>_<ts>.mp3
transcript writer → calls/transcripts/call_<scenario>_<ts>.txt
   ▼
analyze.py (offline, not latency-sensitive):
   transcript → LLM with QA rubric → structured bug candidates (JSON + markdown)
   appended to docs/BUG_REPORT.md for human review/curation
```

## Latency notes (why speech-to-speech)

A cascaded STT→LLM→TTS pipeline needs careful streaming to stay under ~800ms
turn latency. The Realtime API collapses the cascade, giving natural pacing and
turn-taking out of the box — the graders' #1 criterion. We spend the saved effort
on scenario design and bug analysis instead.

## Scenario file contract (owned by Claude)

```yaml
id: 01_simple_scheduling
goal: "Book a new-patient appointment next week, any weekday afternoon."
persona:
  name: "Margaret Chen"
  dob: "1958-03-14"
  voice: "alloy"            # Realtime voice id
  temperament: "polite, slightly chatty, mild hearing trouble"
steering:
  - "If offered a morning slot, ask for afternoon instead."
  - "Accept the second concrete time offered."
  - "Confirm the final date/time back in your own words before ending."
success: "Call ends with a confirmed weekday-afternoon appointment."
edge_case: null              # or e.g. "interrupt the agent mid-sentence twice"
max_seconds: 240
```

## Environment variables (.env)

OPENAI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER,
PUBLIC_BASE_URL, PORT (default 5050). Target number is intentionally NOT an
env var — it is a constant with a guard.
