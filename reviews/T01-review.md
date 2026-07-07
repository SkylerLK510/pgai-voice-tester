# T01 Review — APPROVED (round 2)

## Round 2 verdict: APPROVE — commit `25e57a1` + one direct edit

All four requested changes verified fixed by re-running the fake-socket dry-run
harness against the new code (still no live call, `.env` still absent):

1. `session.update` now uses the GA Realtime shape — `type: "realtime"`,
   `output_modalities: ["audio"]`, nested `audio.input/output` with
   `audio/pcmu`, VAD and voice in their GA locations, no beta keys remaining.
2. The unconditional first `response.create` is gone. Verified: nothing is sent
   until the callee speaks; the 5s silent-callee fallback fires when the far
   end stays quiet and correctly does NOT fire when a greeting arrives first.
3. Goodbye barge-in stall (repro'd in round 1) is fixed: the cancelled goodbye
   is retried once, and after `MAX_GOODBYE_ATTEMPTS` the bridge finishes and
   hangs up regardless. The `finally` block now always attempts REST hangup.
   Re-ran the exact repro: closes and hangs up in <3s. Normal `end_call` path
   regression-checked clean.
4. Outer `asyncio.TimeoutError` is now caught in `main()`.

**Direct edit by reviewer (1 line, per small-fix allowance):** Codex set
`OPENAI_REALTIME_MODEL = "gpt-realtime-2.1"` — I could not confirm that model
id exists and an invalid id fails at websocket connect, mid-call-setup. Changed
to the GA alias `gpt-realtime`, which is guaranteed valid; bump to a dated
snapshot later if the smoke test justifies it.

**Precondition before the first live call (operator):** populate `.env`
(copy `.env.example`) — then I will run a direct Realtime-session smoke test
with the real key (connects and configures a session only; no Twilio, no dial)
to confirm the GA shape is accepted, plus verify the ngrok `PUBLIC_BASE_URL`.

Merged to main.

---

# Round 1 — CHANGES REQUESTED (historical)

Reviewed commit `fbb3331` on `ticket/T01` (707 insertions: `src/call_bridge.py`,
`src/run_call.py`, `src/scenario.py`, requirements, handoff note).

## What passed (dry-run, no call placed)

- Compile check, and all 14 scenario YAMLs load through the Pydantic contract.
- **Safety guard verified with a fake Twilio client**: `+18054398009`, `911`,
  formatted variants — all rejected with ValueError *before* any Twilio call;
  the accepted path dials the hardcoded constant (never the argument), with
  `record=True, recording_channels="dual"` and correct `<Connect><Stream>`
  TwiML. Env-override refusal (`TARGET_NUMBER` etc.) is a nice touch.
- **Bridge integration dry-run** (scripted fake OpenAI + Twilio sockets):
  inbound media → `input_audio_buffer.append` passthrough, audio deltas →
  Twilio media frames, barge-in sends `clear` + `response.cancel`, live
  `[mm:ss] SPEAKER:` logging works, mark-based flush before hangup works, and
  the normal `end_call` path hangs up via REST and exits cleanly.
- uvicorn app boots and shuts down cleanly; `/media-stream` route present.
- No secrets in the diff. `.env` is not yet populated on this machine, so the
  ngrok URL could not be verified — must be done before the first live call.

## Changes requested (priority order)

1. **Realtime protocol shape vs. model — must resolve before the first live
   call.** The bridge connects to `wss://api.openai.com/v1/realtime?model=gpt-realtime`
   (GA model) with **no `OpenAI-Beta: realtime=v1` header**, but sends the
   *beta*-shaped `session.update` (`input_audio_format`, `modalities`, `voice`,
   `temperature` at session root). The GA interface renamed these
   (`audio.input.format`, `output_modalities`, etc.). If the server rejects the
   beta fields, the session silently stays at PCM16 defaults and the call is
   pure static — the reader already tolerates both `response.audio.delta` and
   `response.output_audio.delta`, which suggests this ambiguity is known. Pick
   one interface and match model + header + session shape to it, then verify
   with the real API key by opening a Realtime session directly (no Twilio,
   no dial — costs cents). I can supply my dry-run harness for this.
2. **Patient speaks over the callee's greeting.** `_configure_openai_session`
   fires `response.create` immediately, so the patient starts talking the
   moment the stream opens — while the office agent is delivering its greeting.
   Every call will open with a collision and a clipped patient utterance, which
   is the worst possible first impression for call-audio naturalness. Remove
   the unconditional `response.create` and let server VAD (`create_response:
   true`) respond after the greeting; add a fallback (e.g. if no far-end audio
   within ~5s of stream start, then `response.create`) so a silent callee
   doesn't deadlock two bots waiting for each other.
3. **Goodbye barge-in stall — reproduced.** If the far end speaks after a
   goodbye is requested but before its first audio delta, `_handle_barge_in`
   cancels the goodbye; `_can_finish_closing_response` then requires
   `bot_audio_sent`, which never becomes true → no hangup, `done` never set,
   and `run_call` sits until the outer `max_seconds + 120` timeout. Fix both
   layers: (a) when `closing` and a response finishes with no audio sent,
   re-issue the goodbye once, then finish regardless; (b) make the bridge's
   `finally` always attempt the REST hangup when `call_sid` is set and the call
   isn't hung up — today it's gated on `hangup_started`, so this path leaks the
   call. Repro: send `end_call` with no response in flight, then
   `response.created` → `speech_started` → `response.done`.
4. *(minor)* `asyncio.TimeoutError` from `run()`'s outer `wait_for` isn't in
   `main()`'s caught exceptions — a stalled call ends as a raw traceback
   instead of a clean message.

Not blocking: the `try/except TypeError` header-arg fallback in
`_connect_openai` would be simpler as a pinned `websockets` version in
requirements — take it or leave it.

Everything else — structure, single-writer state, mark accounting, scenario
validation, the guard — is in good shape. With items 1–3 addressed this
approves quickly; none of them require restructuring.
