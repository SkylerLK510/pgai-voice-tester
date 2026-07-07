# T02 Review — APPROVED

Reviewed commit `21d5e97` on `ticket/T02` (`src/recording.py` new, small hooks
into `run_call.py` / `call_bridge.py`, README). No live call placed.

## Verified (dry-run)

- **Live path untouched in any way that matters**: the only bridge change is
  `_log_utterance` appending a `TranscriptLine` before printing — no added
  latency, no new awaits in the audio path.
- **recording.py unit-tested with fakes**: path building + scenario-id
  sanitization (and empty-id guard), `[MM:SS] SPEAKER:` formatting, sort-by-
  timestamp, empty-transcript handling, poll loop (processing→completed,
  `absent` raises with error code, timeout raises with last status, latest of
  multiple recordings picked), download URL carries `RequestedChannels=2` for
  the dual-channel MP3, HTTP basic auth uses account SID + token, empty
  download body raises.
- **Bridge regression**: transcript list accumulates AGENT/PATIENT lines in
  order and the normal `end_call` → hangup path is still clean with the new
  `BridgeConfig.transcript` field.
- Safety guard unchanged; no secrets introduced; auth token never logged.

## Direct edit by reviewer (small-fix allowance, ~8 lines)

`run_call.run()` wrote the transcript only on the happy path — a stalled call,
outer timeout, or operator Ctrl-C lost the entire transcript, and failed calls
are precisely the ones a bug-finding harness must keep evidence for. Moved the
transcript write into the `finally` block (guarded on non-empty). Recording
download stays in the `try`: it needs a completed call and can poll up to
120s, which we don't want on the abort path.

## Notes (non-blocking)

- AGENT line timestamps are stamped when Whisper transcription *completes*,
  so they can lag the actual speech by a second or two. Fine for the ticket's
  "roughly match audio" bar; the analyzer (T03) shouldn't treat them as exact.
- Acceptance item "MP3 has both voices" is unverifiable without a live call —
  will be confirmed by ear on T01/T02's first real run.

Merged to main.
