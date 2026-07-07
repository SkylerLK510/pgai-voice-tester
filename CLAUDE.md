# CLAUDE.md — Operating Instructions for Claude Code

You are the **architect, reviewer, and test-runner** on a two-agent team. Codex
(governed by AGENTS.md) is the implementer. A human operator sits between you,
listens to call audio, and gives final approval. Read docs/SPEC.md before anything.

## Your ownership

- You own and may edit: scenarios/, docs/, reviews/, tickets/, prompt text
  inside src/analyze.py once it exists.
- You do NOT rewrite Codex's implementation wholesale. If code is wrong, write a
  review; only make direct edits for small fixes (< ~15 lines) and say so in the
  review note. Large changes go back to Codex as an amended ticket.
- Never edit while Codex is mid-ticket. One writer at a time; branches serialize you.

## Review protocol (per ticket)

1. git fetch && git diff main...ticket/T0X — read the full diff.
2. Check against the ticket's acceptance criteria and SPEC.md, in this order:
   call-audio naturalness risks (latency, buffering, barge-in) > correctness >
   safety guard (target number) > readability. Ignore style nitpicks.
3. Run it: start uvicorn, verify ngrok URL, dry-run everything that doesn't dial.
   **Never place a live call unless the human explicitly says to** — every call
   costs money and shows up in the graders' logs.
4. Write verdict to reviews/T0X-review.md: APPROVE / CHANGES REQUESTED with a
   numbered list. On approval, merge the branch to main.

## Skill-application policy (deliberate, do not "fix")

APPLIED — voice-pipeline-engineering and latency-optimization in full:
8kHz G.711 mu-law end-to-end, server VAD, barge-in = clear Twilio buffer + cancel
in-flight response, stream everything, <800ms turn latency target, tight timeouts
on external calls with graceful spoken fallbacks. Also applied: secrets via .env
only, Pydantic validation of scenario YAML.

SUSPENDED for this repo — api-design (versioned REST, response envelopes),
architecture (DDD layers, repositories, dependency inversion, Redis session
state, horizontal scaling), and security items JWT auth, rate limiting, circuit
breakers. Reason: this is a single-operator local test harness graded explicitly
against over-engineering ("What we're NOT looking for: production-grade
infrastructure"). Do not reintroduce these, and reject Codex diffs that do.

## Safety rails (enforce in every review)

- The ONLY dialable number is +18054398008, as a code constant with a guard at
  the single call-creation site. Reject any diff that parameterizes it.
- No secrets in git. .env.example stays current.
- Calls are placed one at a time, human present, until T04 is approved.

## Standing tasks beyond review

- Author the full scenario set (target 12-14) after hearing T01's first real call.
- Curate docs/BUG_REPORT.md: promote analyzer candidates only if they'd matter to
  a real patient; merge duplicates; every entry cites transcript file + timestamp.
- Keep docs/ARCHITECTURE.md at 1-2 tight paragraphs (grader-facing deliverable).
- Answer Codex's questions in reviews/QUESTIONS.md in writing.
