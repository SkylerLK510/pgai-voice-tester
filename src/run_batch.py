"""Run scenario calls sequentially and write a call-artifact index."""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .analyze import analyze_transcript, write_analysis_outputs
from .run_call import CallResult, Settings, load_settings, run as run_call
from .scenario import load_scenario


MIN_GAP_SECONDS = 30
DEFAULT_GAP_SECONDS = 30
CALL_INDEX_PATH = Path("calls/index.md")


@dataclass(frozen=True)
class BatchEntry:
    """One completed call row in the generated index."""

    scenario_path: Path
    scenario_id: str
    duration_seconds: int
    recording_path: Path
    transcript_path: Path
    bug_count: int  # -1 = analysis failed during the batch; backfill via src.analyze


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description="Run patient-call scenarios sequentially.")
    parser.add_argument("scenarios_dir", help="Directory containing scenario .yaml files")
    parser.add_argument(
        "--gap-seconds",
        type=int,
        default=DEFAULT_GAP_SECONDS,
        help=f"Delay after each call before the next one (minimum {MIN_GAP_SECONDS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and list scenarios without loading credentials or placing calls",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(Path(args.scenarios_dir), args.gap_seconds, args.dry_run))
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


async def run(scenarios_dir: Path, gap_seconds: int, dry_run: bool = False) -> None:
    """Run every scenario in filename order with a mandatory inter-call gap."""

    _validate_gap(gap_seconds)
    scenario_paths = _discover_scenarios(scenarios_dir)
    scenario_ids = _validate_scenarios(scenario_paths)

    if dry_run:
        _print_dry_run(scenario_paths, scenario_ids, gap_seconds)
        return

    load_dotenv()
    settings = load_settings()
    entries: list[BatchEntry] = []

    for position, scenario_path in enumerate(scenario_paths):
        if position:
            print(f"Waiting {gap_seconds} seconds before the next call...")
            await asyncio.sleep(gap_seconds)

        scenario_id = scenario_ids[position]
        print(f"Running {position + 1}/{len(scenario_paths)}: {scenario_id}")
        call_result = await run_call(scenario_path, settings=settings)
        entry = await _analyze_call(scenario_path, call_result, settings)
        entries.append(entry)
        write_call_index(entries)
        print(f"Call index updated: {CALL_INDEX_PATH}")

    print(f"Batch complete: {len(entries)} calls")


async def _analyze_call(
    scenario_path: Path,
    call_result: CallResult,
    settings: Settings,
) -> BatchEntry:
    # Analysis is best-effort: the recording and transcript are already on disk,
    # so an analyzer failure must never abort the remaining (expensive) calls.
    bug_count = -1
    try:
        result = await analyze_transcript(call_result.transcript_path, settings.openai_api_key)
        analysis_paths = write_analysis_outputs(result, call_result.transcript_path)
        print(f"Analysis JSON written: {analysis_paths.json_path}")
        print(f"Bug report appended: {analysis_paths.report_path}")
        bug_count = len(result.bugs)
    except Exception as exc:
        print(
            f"WARNING: analysis failed for {call_result.transcript_path} ({exc}); "
            f"backfill with: python -m src.analyze {call_result.transcript_path}"
        )

    return BatchEntry(
        scenario_path=scenario_path,
        scenario_id=call_result.scenario_id,
        duration_seconds=call_result.duration_seconds,
        recording_path=call_result.recording_path,
        transcript_path=call_result.transcript_path,
        bug_count=bug_count,
    )


def write_call_index(entries: list[BatchEntry], index_path: Path = CALL_INDEX_PATH) -> Path:
    """Write links and outcomes for completed calls in the current batch."""

    index_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Call Index",
        "",
        "| Scenario | Duration | Recording | Transcript | Bug count |",
        "| --- | ---: | --- | --- | ---: |",
    ]

    for entry in entries:
        scenario_link = _markdown_link(entry.scenario_id, entry.scenario_path, index_path)
        recording_link = _markdown_link("MP3", entry.recording_path, index_path)
        transcript_link = _markdown_link("TXT", entry.transcript_path, index_path)
        bug_cell = str(entry.bug_count) if entry.bug_count >= 0 else "pending"
        lines.append(
            f"| {scenario_link} | {_format_duration(entry.duration_seconds)} | "
            f"{recording_link} | {transcript_link} | {bug_cell} |"
        )

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path


def _discover_scenarios(scenarios_dir: Path) -> list[Path]:
    if not scenarios_dir.exists():
        raise FileNotFoundError(f"Scenario directory not found: {scenarios_dir}")
    if not scenarios_dir.is_dir():
        raise ValueError(f"Scenario path is not a directory: {scenarios_dir}")

    paths = sorted(path for path in scenarios_dir.glob("*.yaml") if path.is_file())
    if not paths:
        raise FileNotFoundError(f"No scenario .yaml files found in {scenarios_dir}")
    return paths


def _validate_scenarios(scenario_paths: list[Path]) -> list[str]:
    scenario_ids: list[str] = []
    seen_ids: set[str] = set()

    for path in scenario_paths:
        scenario = load_scenario(path)
        if scenario.id in seen_ids:
            raise ValueError(f"Duplicate scenario id {scenario.id!r}: {path}")
        seen_ids.add(scenario.id)
        scenario_ids.append(scenario.id)

    return scenario_ids


def _validate_gap(gap_seconds: int) -> None:
    if gap_seconds < MIN_GAP_SECONDS:
        raise ValueError(
            f"--gap-seconds must be at least {MIN_GAP_SECONDS}; calls must never run back-to-back"
        )


def _print_dry_run(
    scenario_paths: list[Path], scenario_ids: list[str], gap_seconds: int
) -> None:
    print("DRY RUN: no calls will be placed")
    print(f"Validated {len(scenario_paths)} scenarios; gap={gap_seconds} seconds")
    for position, (path, scenario_id) in enumerate(zip(scenario_paths, scenario_ids), start=1):
        print(f"{position:02d}. {scenario_id} ({path})")


def _markdown_link(label: str, target: Path, index_path: Path) -> str:
    relative_target = Path(os.path.relpath(target, start=index_path.parent)).as_posix()
    return f"[{label}]({relative_target})"


def _format_duration(duration_seconds: int) -> str:
    minutes, seconds = divmod(max(0, duration_seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"


if __name__ == "__main__":
    main()
