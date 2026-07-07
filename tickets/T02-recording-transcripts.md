# T02 — Recordings + transcripts

- Enable Twilio dual-channel recording on call creation.
- `src/recording.py`: after hangup, poll until recording is ready, download MP3 to
  calls/recordings/call_<scenario_id>_<YYYYMMDD-HHMMSS>.mp3
- Write transcript to calls/transcripts/ same basename .txt, format:
  `[MM:SS] PATIENT: ...` / `[MM:SS] AGENT: ...`
- Update README with any new setup steps.

Acceptance: after one run, both files exist, MP3 has both voices, transcript
timestamps roughly match audio.
