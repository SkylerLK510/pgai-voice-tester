"""Run one patient-simulator call from a scenario file."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from .call_bridge import BridgeConfig, create_app
from .recording import (
    TranscriptLine,
    build_output_paths,
    download_call_recording,
    write_transcript,
)
from .scenario import load_scenario


TARGET_NUMBER = "+18054398008"
MEDIA_STREAM_PATH = "/media-stream"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    public_base_url: str
    port: int


def main() -> None:
    """CLI entry point."""

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m src.run_call scenarios/<file>.yaml")
    try:
        asyncio.run(run(Path(sys.argv[1])))
    except (asyncio.TimeoutError, FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


async def run(scenario_path: Path) -> None:
    load_dotenv()
    settings = load_settings()
    scenario = load_scenario(scenario_path)

    done = asyncio.Event()
    transcript: list[TranscriptLine] = []
    twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    output_paths = build_output_paths(scenario.id)
    app = create_app(
        BridgeConfig(
            scenario=scenario,
            openai_api_key=settings.openai_api_key,
            twilio_client=twilio_client,
            done=done,
            transcript=transcript,
        )
    )

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="0.0.0.0",
            port=settings.port,
            log_level="warning",
            ws="websockets",
        )
    )
    server_task = asyncio.create_task(server.serve())
    await _wait_for_server(server)

    try:
        call_sid = await asyncio.to_thread(
            create_outbound_call,
            twilio_client,
            settings.twilio_from_number,
            _media_stream_url(settings.public_base_url),
            TARGET_NUMBER,
        )
        print(f"Outbound call placed: call_sid={call_sid} target={TARGET_NUMBER}")
        await asyncio.wait_for(done.wait(), timeout=scenario.max_seconds + 120)
        transcript_path = write_transcript(transcript, output_paths.transcript_path)
        print(f"Transcript written: {transcript_path}")
        recording_path = await download_call_recording(
            twilio_client,
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            call_sid,
            output_paths.recording_path,
        )
        print(f"Recording downloaded: {recording_path}")
    finally:
        server.should_exit = True
        await server_task


def load_settings() -> Settings:
    """Load required settings from .env-backed environment variables."""

    _refuse_target_overrides()
    return Settings(
        openai_api_key=_required_env("OPENAI_API_KEY"),
        twilio_account_sid=_required_env("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=_required_env("TWILIO_AUTH_TOKEN"),
        twilio_from_number=_required_env("TWILIO_FROM_NUMBER"),
        public_base_url=_valid_public_base_url(_required_env("PUBLIC_BASE_URL")),
        port=_valid_port(os.getenv("PORT", "5050")),
    )


def create_outbound_call(
    twilio_client: Client,
    from_number: str,
    media_stream_url: str,
    target_number: str,
) -> str:
    """Create the only outbound call this project is allowed to make."""

    if _normalize_phone_number(target_number) != TARGET_NUMBER:
        raise ValueError(f"Refusing to dial {target_number}; only {TARGET_NUMBER} is allowed")

    response = VoiceResponse()
    connect = Connect()
    connect.append(Stream(url=media_stream_url))
    response.append(connect)

    call = twilio_client.calls.create(
        to=TARGET_NUMBER,
        from_=from_number,
        twiml=str(response),
        record=True,
        recording_channels="dual",
    )
    return str(call.sid)


async def _wait_for_server(server: uvicorn.Server) -> None:
    for _ in range(100):
        if server.started:
            return
        await asyncio.sleep(0.05)
    raise RuntimeError("uvicorn did not start within 5 seconds")


def _media_stream_url(public_base_url: str) -> str:
    return public_base_url.rstrip("/").replace("https://", "wss://", 1) + MEDIA_STREAM_PATH


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def _refuse_target_overrides() -> None:
    for name in ("TARGET_NUMBER", "TWILIO_TO_NUMBER", "TO_NUMBER"):
        if os.getenv(name):
            raise RuntimeError(
                f"{name} is not supported. The only dialable target is hardcoded as {TARGET_NUMBER}."
            )


def _valid_public_base_url(value: str) -> str:
    if not value.startswith("https://"):
        raise RuntimeError("PUBLIC_BASE_URL must be an https:// ngrok or public tunnel URL")
    return value.rstrip("/")


def _valid_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise RuntimeError("PORT must be an integer") from exc
    if port < 1 or port > 65535:
        raise RuntimeError("PORT must be between 1 and 65535")
    return port


def _normalize_phone_number(value: str) -> str:
    return "+" + "".join(ch for ch in value if ch.isdigit())


if __name__ == "__main__":
    main()
