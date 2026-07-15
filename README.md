# PGAI Patient Simulator

Automated "patient" voice bot that calls the Pretty Good AI test line, holds natural
conversations from scenario files, records + transcribes calls, and flags bugs.

## Setup (once)
1. `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. Copy `.env.example` → `.env`, fill values.
3. `ngrok http 5050` and put the https URL in PUBLIC_BASE_URL.

## Run a call
```
python -m src.run_call scenarios/01_simple_scheduling.yaml
```

After the call hangs up, the runner writes:
- `calls/recordings/call_<scenario_id>_<YYYYMMDD-HHMMSS>.mp3`
- `calls/transcripts/call_<scenario_id>_<YYYYMMDD-HHMMSS>.txt`

## Analyze transcripts
```
python -m src.analyze calls/transcripts/<file>.txt
python -m src.analyze --all
```

Analyzer JSON goes to `calls/analysis/`, and unreviewed markdown entries are appended
to `docs/BUG_REPORT.md`.

## Run a batch
```sh
python -m src.run_batch scenarios/
```

Only run the live batch in an operator-attended session, after at least three clean
single calls placed in that same sitting. During development, use `--dry-run` only.

Batch calls run sequentially with a 30-second gap, and each completed transcript is
analyzed before the next call. Use `--gap-seconds N` to increase the gap; values below
30 are refused. The runner writes a linked summary to `calls/index.md`.

Validate the scenario order and pacing without credentials or phone calls:
```sh
python -m src.run_batch scenarios/ --dry-run
```

See `docs/SPEC.md` for architecture, `AGENTS.md` for the coding-agent workflow.
