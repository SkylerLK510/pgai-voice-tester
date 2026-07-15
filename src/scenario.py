"""Scenario loading and patient prompt construction."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Persona(BaseModel):
    """Patient persona fields owned by the scenario file."""

    model_config = ConfigDict(extra="forbid")

    name: str
    dob: str
    voice: str = "alloy"
    temperament: str

    @field_validator("name", "dob", "voice", "temperament")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()


class Scenario(BaseModel):
    """Validated scenario contract from docs/SPEC.md."""

    model_config = ConfigDict(extra="forbid")

    id: str
    goal: str
    persona: Persona
    steering: list[str] = Field(default_factory=list)
    success: str
    edge_case: str | None = None
    max_seconds: int = 240

    @field_validator("id", "goal", "success")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("steering")
    @classmethod
    def _valid_steering(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != len(value):
            raise ValueError("steering entries must not be empty")
        return cleaned

    @field_validator("max_seconds")
    @classmethod
    def _valid_duration(cls, value: int) -> int:
        if value < 30 or value > 600:
            raise ValueError("max_seconds must be between 30 and 600")
        return value


def load_scenario(path: str | Path) -> Scenario:
    """Load and validate a scenario YAML file."""

    scenario_path = Path(path)
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

    with scenario_path.open("r", encoding="utf-8") as file:
        raw: Any = yaml.safe_load(file)

    if not isinstance(raw, dict):
        raise ValueError(f"Scenario file must contain a YAML mapping: {scenario_path}")

    try:
        return Scenario.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"Invalid scenario {scenario_path}: {exc}") from exc


def build_patient_prompt(scenario: Scenario) -> str:
    """Build the Realtime system prompt for the patient voice."""

    steering = "\n".join(f"- {item}" for item in scenario.steering)
    edge_case = scenario.edge_case or "None"

    return f"""You are a real patient calling a healthcare office AI agent.

Patient:
- Name: {scenario.persona.name}
- Date of birth: {scenario.persona.dob}
- Temperament: {scenario.persona.temperament}

Call goal:
{scenario.goal}

Scenario steering:
{steering}

Success condition:
{scenario.success}

Edge case to exercise:
{edge_case}

Conversation rules:
- Speak English only, for the entire call. Never switch languages, even if you
  hear menu prompts, offers, or speech in another language ("para Español..."),
  and even if asked. If offered another language, decline and continue in English.
- Sound like a natural human patient on a phone call, with brief backchannels and normal hesitation.
- Do not announce that you are an AI, a test harness, a scenario, or using these instructions.
- Do not dump every detail up front. Offer information when it fits the agent's question.
- Keep turns concise enough for phone conversation, usually one or two sentences.
- If the agent talks while you need to interrupt, barge in naturally according to the scenario.
- When the success condition is satisfied, confirm the important details, say a brief natural goodbye, then call the end_call tool.
- If the call is clearly going nowhere, say a brief natural goodbye, then call the end_call tool.
"""
