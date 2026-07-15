# Live-call session checklist (operator-attended, screen-recorded)

Everything before "Single calls" is dial-free. Nothing below places a call
until the operator says go; calls are one at a time with the operator present.

## Pre-flight (no dialing)

- [ ] `.env` populated; `python -m src.run_batch scenarios/ --dry-run` lists 14 scenarios
- [ ] uvicorn up; ngrok tunnel live and `PUBLIC_BASE_URL` matches it
- [ ] Screen recording started: macOS built-in (⌘⇧5 → Record Entire Screen →
      Options → Microphone on). The recorder captures mic only, so play call
      MP3s through speakers during review so they land in the recording.

## Single calls — at least 3 clean, one at a time

Suggested order (baseline → engineering showcase → safety):

1. `01_simple_scheduling` — baseline flow
2. `07_barge_in` — interrupt handling; listen for buffer-clear + cancel feel
3. `08_emergency_redirect` — safety behavior under an emergency mention

Listen for on every call: turn latency (should feel sub-second), natural
turn-taking (no talk-over, no dead air), clean barge-in, natural goodbye + hangup.

After each call:
- [ ] MP3 in `calls/recordings/` is dual-channel (patient one side, agent other)
- [ ] Transcript in `calls/transcripts/` has timestamps and both speakers
- [ ] `python -m src.analyze calls/transcripts/<file>.txt` produces sane candidates

A call is "clean" when the harness behaved (audio, pacing, artifacts) — agent
bugs found are a success, not a failure.

## Batch — only after 3 clean singles in this same sitting

- [ ] `python -m src.run_batch scenarios/` (30s minimum gap enforced; operator stays present)
- [ ] Watch for `WARNING: analysis failed` lines — backfill those transcripts with
      `python -m src.analyze <transcript>` after the batch; index rows show "pending"
- [ ] If a call fails mid-batch: completed rows survive in `calls/index.md`; copy the
      remaining YAMLs to a temp dir and point `run_batch` at it to resume

## Wrap-up

- [ ] Review `calls/index.md` links all resolve
- [ ] Claude curates analyzer output in `docs/BUG_REPORT.md` (dedupe, drop nitpicks,
      cite transcript + timestamp per entry)
- [ ] Stop the screen recording (menu-bar stop button); upload the .mov to
      Google Drive and note the share link alongside the submission
