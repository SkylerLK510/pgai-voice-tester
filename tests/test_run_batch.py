"""Regression checks for batch pacing and index generation."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import src.run_batch as batch
from src.analyze import AnalysisPaths, AnalysisResult, BugCandidate
from src.run_call import CallResult, Settings


class BatchRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_sequentially_with_gap_and_updates_index(self) -> None:
        scenario_paths = [
            Path("scenarios/01_simple_scheduling.yaml"),
            Path("scenarios/02_reschedule.yaml"),
        ]
        settings = Settings(
            "openai",
            "AC123",
            "token",
            "+15555550100",
            "https://example.ngrok.app",
            5050,
        )
        call_results = [
            CallResult(
                "01_simple_scheduling",
                61,
                Path("calls/recordings/one.mp3"),
                Path("calls/transcripts/one.txt"),
            ),
            CallResult(
                "02_reschedule",
                125,
                Path("calls/recordings/two.mp3"),
                Path("calls/transcripts/two.txt"),
            ),
        ]
        analyses = [
            AnalysisResult(transcript_file="one.txt", bugs=[]),
            AnalysisResult(
                transcript_file="two.txt",
                bugs=[
                    BugCandidate(
                        severity="med",
                        dimension="factual consistency",
                        timestamp="00:42",
                        expected="Keep the confirmed date consistent.",
                        actual="Changed the confirmed date.",
                        reproduction_hint="Confirm a date, then ask the agent to repeat it.",
                    )
                ],
            ),
        ]
        run_call = AsyncMock(side_effect=call_results)
        analyze = AsyncMock(side_effect=analyses)
        sleep = AsyncMock()
        write_outputs = Mock(
            side_effect=[
                AnalysisPaths(Path("calls/analysis/one.json"), Path("docs/BUG_REPORT.md")),
                AnalysisPaths(Path("calls/analysis/two.json"), Path("docs/BUG_REPORT.md")),
            ]
        )
        indexed_entry_counts: list[int] = []
        indexed_bug_counts: list[int] = []

        def capture_index(entries: list[batch.BatchEntry]) -> None:
            indexed_entry_counts.append(len(entries))
            indexed_bug_counts.append(entries[-1].bug_count)

        write_index = Mock(side_effect=capture_index)

        with (
            patch.object(batch, "_discover_scenarios", return_value=scenario_paths),
            patch.object(
                batch,
                "_validate_scenarios",
                return_value=["01_simple_scheduling", "02_reschedule"],
            ),
            patch.object(batch, "load_dotenv"),
            patch.object(batch, "load_settings", return_value=settings),
            patch.object(batch, "run_call", run_call),
            patch.object(batch, "analyze_transcript", analyze),
            patch.object(batch, "write_analysis_outputs", write_outputs),
            patch.object(batch, "write_call_index", write_index),
            patch.object(batch.asyncio, "sleep", sleep),
            redirect_stdout(io.StringIO()),
        ):
            await batch.run(Path("scenarios"), 30)

        self.assertEqual(
            [call.args[0] for call in run_call.await_args_list],
            scenario_paths,
        )
        self.assertTrue(
            all(call.kwargs["settings"] is settings for call in run_call.await_args_list)
        )
        sleep.assert_awaited_once_with(30)
        self.assertEqual(indexed_entry_counts, [1, 2])
        self.assertEqual(indexed_bug_counts, [0, 1])

    async def test_dry_run_never_loads_credentials_or_calls(self) -> None:
        output = io.StringIO()
        with (
            patch.object(batch, "load_settings") as load_settings,
            patch.object(batch, "run_call", new_callable=AsyncMock) as run_call,
            redirect_stdout(output),
        ):
            await batch.run(Path("scenarios"), 30, dry_run=True)

        load_settings.assert_not_called()
        run_call.assert_not_awaited()
        self.assertIn("DRY RUN: no calls will be placed", output.getvalue())
        self.assertIn("Validated 14 scenarios", output.getvalue())

    def test_rejects_gap_below_thirty_seconds(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 30"):
            batch._validate_gap(29)


class CallIndexTests(unittest.TestCase):
    def test_writes_relative_artifact_links_duration_and_bug_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_path = root / "calls" / "index.md"
            entry = batch.BatchEntry(
                scenario_path=root / "scenarios" / "01.yaml",
                scenario_id="01_simple",
                duration_seconds=125,
                recording_path=root / "calls" / "recordings" / "one.mp3",
                transcript_path=root / "calls" / "transcripts" / "one.txt",
                bug_count=2,
            )

            batch.write_call_index([entry], index_path)

            text = index_path.read_text(encoding="utf-8")
            expected_row = (
                "| [01_simple](../scenarios/01.yaml) | 02:05 | "
                "[MP3](recordings/one.mp3) | [TXT](transcripts/one.txt) | 2 |"
            )
            self.assertIn(expected_row, text)


if __name__ == "__main__":
    unittest.main()
