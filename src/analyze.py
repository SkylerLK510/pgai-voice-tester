"""Post-call transcript analyzer."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


ANALYSIS_MODEL = "gpt-5.5"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
TRANSCRIPTS_DIR = Path("calls/transcripts")
ANALYSIS_DIR = Path("calls/analysis")
BUG_REPORT_PATH = Path("docs/BUG_REPORT.md")

RUBRIC = (
    "identity verification, factual consistency within the call, invalid date/time acceptance "
    "(for example weekend appointments), hallucinated policies, failure to answer the actual "
    "question, loops/repetition, mishandled interruptions, inappropriate handling of ambiguity, "
    "call-flow dead ends"
)


class BugCandidate(BaseModel):
    """One analyzer bug candidate."""

    model_config = ConfigDict(extra="forbid")

    severity: str
    dimension: str
    timestamp: str
    expected: str
    actual: str
    reproduction_hint: str

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"high", "med", "low"}:
            raise ValueError("severity must be high, med, or low")
        return value

    @field_validator("dimension", "timestamp", "expected", "actual", "reproduction_hint")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()


class AnalysisResult(BaseModel):
    """Structured analyzer result."""

    model_config = ConfigDict(extra="forbid")

    transcript_file: str
    summary: str = ""
    bugs: list[BugCandidate] = Field(default_factory=list)


@dataclass(frozen=True)
class AnalysisPaths:
    """Output paths for one transcript analysis."""

    json_path: Path
    report_path: Path


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description="Analyze call transcripts for bug candidates.")
    parser.add_argument("transcript", nargs="?", help="Path to one transcript .txt file")
    parser.add_argument("--all", action="store_true", help="Analyze every transcript in calls/transcripts/")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.transcript, args.all))
    except (FileNotFoundError, RuntimeError, ValueError, ValidationError) as exc:
        raise SystemExit(str(exc)) from exc


async def run(transcript_arg: str | None, analyze_all: bool) -> None:
    """Analyze one transcript or all transcripts."""

    load_dotenv()
    transcript_paths = _resolve_transcript_paths(transcript_arg, analyze_all)
    api_key = _required_env("OPENAI_API_KEY")

    for transcript_path in transcript_paths:
        result = await analyze_transcript(transcript_path, api_key)
        paths = write_analysis_outputs(result, transcript_path)
        print(f"Analysis JSON written: {paths.json_path}")
        print(f"Bug report appended: {paths.report_path}")


async def analyze_transcript(
    transcript_path: Path,
    openai_api_key: str,
    model: str = ANALYSIS_MODEL,
) -> AnalysisResult:
    """Send a transcript to the LLM and return validated bug candidates."""

    transcript_text = _read_transcript(transcript_path)
    raw_result = await _call_openai(openai_api_key, model, transcript_path, transcript_text)
    result = AnalysisResult.model_validate(raw_result)
    return result.model_copy(update={"transcript_file": str(transcript_path)})


def write_analysis_outputs(
    result: AnalysisResult,
    transcript_path: Path,
    analysis_dir: Path = ANALYSIS_DIR,
    bug_report_path: Path = BUG_REPORT_PATH,
) -> AnalysisPaths:
    """Write JSON analysis and append markdown report entries."""

    analysis_dir.mkdir(parents=True, exist_ok=True)
    bug_report_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = analysis_dir / f"{transcript_path.stem}_{timestamp}.json"
    payload = result.model_dump()
    payload["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with bug_report_path.open("a", encoding="utf-8") as file:
        file.write(_format_bug_report(result, transcript_path))

    return AnalysisPaths(json_path=json_path, report_path=bug_report_path)


async def _call_openai(
    openai_api_key: str,
    model: str,
    transcript_path: Path,
    transcript_text: str,
) -> dict[str, Any]:
    request = {
        "model": model,
        "instructions": _analysis_instructions(),
        "input": _analysis_input(transcript_path, transcript_text),
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "bug_analysis",
                "strict": True,
                "schema": _analysis_schema(),
            }
        },
    }
    headers = {"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.post(OPENAI_RESPONSES_URL, headers=headers, json=request)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenAI analysis request failed: {exc}") from exc

    output_text = _extract_output_text(response.json())
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI returned invalid JSON: {exc}") from exc


def _analysis_instructions() -> str:
    return f"""You are a healthcare AI voice-agent QA reviewer.

Analyze transcripts from test calls where PATIENT is the simulated caller and AGENT is the healthcare office AI.

Rubric dimensions: {RUBRIC}.

Return only concrete, user-impacting AGENT behavior bugs. Ignore minor wording preferences, harmless awkwardness, and issues caused by missing audio context. If the transcript does not support a bug, omit it.

Severity:
- high: safety, privacy/identity, materially wrong appointment/medical/admin outcome, or a call dead end that blocks the patient.
- med: confusing or incorrect behavior that a patient could recover from.
- low: minor but real quality issue worth human review.
"""


def _analysis_input(transcript_path: Path, transcript_text: str) -> str:
    return f"""Transcript file: {transcript_path}

Transcript:
{transcript_text}
"""


def _analysis_schema() -> dict[str, Any]:
    bug_schema = {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": ["high", "med", "low"]},
            "dimension": {"type": "string"},
            "timestamp": {"type": "string"},
            "expected": {"type": "string"},
            "actual": {"type": "string"},
            "reproduction_hint": {"type": "string"},
        },
        "required": [
            "severity",
            "dimension",
            "timestamp",
            "expected",
            "actual",
            "reproduction_hint",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "transcript_file": {"type": "string"},
            "summary": {"type": "string"},
            "bugs": {"type": "array", "items": bug_schema},
        },
        "required": ["transcript_file", "summary", "bugs"],
        "additionalProperties": False,
    }


def _extract_output_text(response_json: dict[str, Any]) -> str:
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"]

    chunks: list[str] = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])

    text = "".join(chunks).strip()
    if not text:
        raise RuntimeError("OpenAI response did not contain output text")
    return text


def _format_bug_report(result: AnalysisResult, transcript_path: Path) -> str:
    analyzed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "",
        f"## UNREVIEWED - {transcript_path.name} - {analyzed_at}",
        "",
    ]

    if result.summary:
        lines.extend([result.summary, ""])

    if not result.bugs:
        lines.extend(["No bug candidates returned.", ""])
        return "\n".join(lines)

    for bug in result.bugs:
        lines.extend(
            [
                f"### [{bug.severity.upper()}] {bug.dimension} at {bug.timestamp}",
                f"- Transcript: `{transcript_path}`",
                f"- Expected: {bug.expected}",
                f"- Actual: {bug.actual}",
                f"- Repro: {bug.reproduction_hint}",
                "",
            ]
        )

    return "\n".join(lines)


def _resolve_transcript_paths(transcript_arg: str | None, analyze_all: bool) -> list[Path]:
    if analyze_all and transcript_arg:
        raise ValueError("Use either a transcript path or --all, not both")
    if not analyze_all and not transcript_arg:
        raise ValueError("Usage: python -m src.analyze calls/transcripts/<file>.txt or --all")

    if analyze_all:
        paths = sorted(path for path in TRANSCRIPTS_DIR.glob("*.txt") if path.is_file())
        if not paths:
            raise FileNotFoundError(f"No transcript .txt files found in {TRANSCRIPTS_DIR}")
        return paths

    path = Path(transcript_arg or "")
    if not path.exists():
        raise FileNotFoundError(f"Transcript file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Transcript path is not a file: {path}")
    return [path]


def _read_transcript(transcript_path: Path) -> str:
    text = transcript_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Transcript file is empty: {transcript_path}")
    return text


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


if __name__ == "__main__":
    main()
