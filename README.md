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

See `docs/SPEC.md` for architecture, `AGENTS.md` for the coding-agent workflow.
