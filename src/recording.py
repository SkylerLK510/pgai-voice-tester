"""Recording download and transcript file writing."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from twilio.rest import Client


RECORDINGS_DIR = Path("calls/recordings")
TRANSCRIPTS_DIR = Path("calls/transcripts")
RECORDING_POLL_SECONDS = 2.0
RECORDING_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class TranscriptLine:
    """One timestamped call transcript line."""

    elapsed_seconds: int
    speaker: str
    text: str

    def format(self) -> str:
        minutes, seconds = divmod(max(0, self.elapsed_seconds), 60)
        return f"[{minutes:02d}:{seconds:02d}] {self.speaker}: {self.text}"


@dataclass(frozen=True)
class CallOutputPaths:
    """Output paths for one call run."""

    basename: str
    recording_path: Path
    transcript_path: Path


def build_output_paths(scenario_id: str, timestamp: datetime | None = None) -> CallOutputPaths:
    """Build stable recording/transcript paths for a scenario run."""

    timestamp = timestamp or datetime.now()
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", scenario_id).strip("_")
    if not safe_id:
        raise ValueError("scenario_id must contain at least one filename-safe character")

    basename = f"call_{safe_id}_{timestamp.strftime('%Y%m%d-%H%M%S')}"
    return CallOutputPaths(
        basename=basename,
        recording_path=RECORDINGS_DIR / f"{basename}.mp3",
        transcript_path=TRANSCRIPTS_DIR / f"{basename}.txt",
    )


def write_transcript(lines: list[TranscriptLine], transcript_path: Path) -> Path:
    """Write timestamped transcript lines to disk."""

    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(lines, key=lambda line: line.elapsed_seconds)
    text = "\n".join(line.format() for line in ordered)
    transcript_path.write_text(f"{text}\n" if text else "", encoding="utf-8")
    return transcript_path


async def download_call_recording(
    twilio_client: Client,
    account_sid: str,
    auth_token: str,
    call_sid: str,
    recording_path: Path,
    timeout_seconds: float = RECORDING_TIMEOUT_SECONDS,
) -> Path:
    """Poll Twilio until a call recording is complete, then download dual-channel MP3."""

    recording = await _wait_for_completed_recording(twilio_client, call_sid, timeout_seconds)
    if not recording.sid:
        raise RuntimeError(f"Twilio returned a completed recording with no SID for call {call_sid}")

    recording_path.parent.mkdir(parents=True, exist_ok=True)
    url = _recording_media_url(account_sid, recording.sid)

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, auth=(account_sid, auth_token))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to download Twilio recording {recording.sid}: {exc}") from exc

    recording_path.write_bytes(response.content)

    if recording_path.stat().st_size == 0:
        raise RuntimeError(f"Downloaded recording is empty: {recording_path}")

    return recording_path


async def _wait_for_completed_recording(
    twilio_client: Client,
    call_sid: str,
    timeout_seconds: float,
) -> Any:
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    while True:
        recordings = await asyncio.to_thread(twilio_client.recordings.list, call_sid=call_sid, limit=20)
        recording = _latest_recording(recordings)

        if recording and recording.status == "completed":
            return recording
        if recording and recording.status == "absent":
            raise RuntimeError(
                f"Twilio recording {recording.sid} is absent for call {call_sid}; "
                f"error_code={recording.error_code}"
            )
        if asyncio.get_running_loop().time() >= deadline:
            status = getattr(recording, "status", "not found") if recording else "not found"
            raise RuntimeError(
                f"Timed out waiting for Twilio recording for call {call_sid}; last status={status}"
            )

        await asyncio.sleep(RECORDING_POLL_SECONDS)


def _latest_recording(recordings: list[Any]) -> Any | None:
    if not recordings:
        return None
    return max(recordings, key=_recording_sort_key)


def _recording_sort_key(recording: Any) -> float:
    if not recording.date_created:
        return 0.0
    return recording.date_created.timestamp()


def _recording_media_url(account_sid: str, recording_sid: str) -> str:
    return (
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/"
        f"Recordings/{recording_sid}.mp3?RequestedChannels=2"
    )
