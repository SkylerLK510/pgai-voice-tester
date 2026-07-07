"""Twilio Media Streams to OpenAI Realtime bridge."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from twilio.rest import Client

from .scenario import Scenario, build_patient_prompt


OPENAI_REALTIME_MODEL = "gpt-realtime"
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
OPENAI_AUDIO_FORMAT = "audio/pcmu"
INITIAL_GREETING_WAIT_SECONDS = 5.0
GOODBYE_FLUSH_SECONDS = 8.0
MAX_GOODBYE_ATTEMPTS = 2


@dataclass
class BridgeConfig:
    """Runtime configuration shared by the single active bridge."""

    scenario: Scenario
    openai_api_key: str
    twilio_client: Client
    done: asyncio.Event


@dataclass
class BridgeState:
    """Mutable call state for one Twilio media stream."""

    started_at: float = field(default_factory=time.monotonic)
    stream_sid: str | None = None
    call_sid: str | None = None
    agent_speech_started: bool = False
    initial_response_sent: bool = False
    response_in_progress: bool = False
    bot_audio_sent: bool = False
    pending_marks: set[str] = field(default_factory=set)
    mark_counter: int = 0
    closing: bool = False
    goodbye_requested: bool = False
    goodbye_attempts: int = 0
    hangup_started: bool = False
    hung_up: bool = False
    close_reason: str = ""
    patient_transcript: list[str] = field(default_factory=list)

    def elapsed(self) -> str:
        seconds = max(0, int(time.monotonic() - self.started_at))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"


def create_app(config: BridgeConfig) -> FastAPI:
    """Create the one-endpoint FastAPI app Twilio connects to."""

    app = FastAPI()

    @app.websocket("/media-stream")
    async def media_stream(websocket: WebSocket) -> None:
        await bridge_media_stream(websocket, config)

    return app


async def bridge_media_stream(twilio_ws: WebSocket, config: BridgeConfig) -> None:
    """Bridge one Twilio WebSocket to one OpenAI Realtime WebSocket."""

    await twilio_ws.accept()
    state = BridgeState()
    openai_ws = await _connect_openai(config.openai_api_key)

    try:
        async with openai_ws:
            await _configure_openai_session(openai_ws, config.scenario)
            tasks = [
                asyncio.create_task(_from_twilio(twilio_ws, openai_ws, state)),
                asyncio.create_task(_from_openai(openai_ws, twilio_ws, config, state)),
                asyncio.create_task(_initial_silence_fallback(openai_ws, config, state)),
                asyncio.create_task(_max_duration_timer(openai_ws, twilio_ws, config, state)),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except WebSocketDisconnect:
        print("Twilio media stream disconnected.")
    except websockets.ConnectionClosed:
        print("OpenAI Realtime connection closed.")
    finally:
        await _hang_up_if_needed(config, state)
        config.done.set()


async def _connect_openai(openai_api_key: str):
    headers = [
        ("Authorization", f"Bearer {openai_api_key}"),
    ]
    url = f"{OPENAI_REALTIME_URL}?model={OPENAI_REALTIME_MODEL}"

    try:
        return await websockets.connect(
            url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=20,
            max_size=None,
        )
    except TypeError:
        return await websockets.connect(
            url,
            extra_headers=headers,
            ping_interval=20,
            ping_timeout=20,
            max_size=None,
        )


async def _configure_openai_session(openai_ws: Any, scenario: Scenario) -> None:
    await _send_openai(
        openai_ws,
        {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": OPENAI_REALTIME_MODEL,
                "instructions": build_patient_prompt(scenario),
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": OPENAI_AUDIO_FORMAT},
                        "transcription": {"model": "whisper-1"},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500,
                            "create_response": True,
                            "interrupt_response": True,
                        },
                    },
                    "output": {
                        "format": {"type": OPENAI_AUDIO_FORMAT},
                        "voice": scenario.persona.voice,
                    },
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "end_call",
                        "description": "End the phone call after the patient has said goodbye.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {
                                    "type": "string",
                                    "description": "Short reason the patient is ready to end the call.",
                                }
                            },
                            "required": ["reason"],
                        },
                    }
                ],
                "tool_choice": "auto",
            },
        },
    )


async def _from_twilio(twilio_ws: WebSocket, openai_ws: Any, state: BridgeState) -> None:
    while True:
        message = json.loads(await twilio_ws.receive_text())
        event = message.get("event")

        if event == "start":
            start = message.get("start", {})
            state.stream_sid = start.get("streamSid")
            state.call_sid = start.get("callSid")
            state.started_at = time.monotonic()
            print(f"Call connected: call_sid={state.call_sid} stream_sid={state.stream_sid}")
        elif event == "media":
            payload = message.get("media", {}).get("payload")
            if payload:
                await _send_openai(
                    openai_ws,
                    {"type": "input_audio_buffer.append", "audio": payload},
                )
        elif event == "mark":
            mark_name = message.get("mark", {}).get("name")
            if mark_name:
                state.pending_marks.discard(mark_name)
        elif event == "stop":
            print("Twilio reported call stop.")
            return


async def _from_openai(
    openai_ws: Any,
    twilio_ws: WebSocket,
    config: BridgeConfig,
    state: BridgeState,
) -> None:
    async for raw in openai_ws:
        event = json.loads(raw)
        event_type = event.get("type")

        if event_type == "response.created":
            state.response_in_progress = True
            state.bot_audio_sent = False
        elif event_type in {"response.audio.delta", "response.output_audio.delta"}:
            state.response_in_progress = True
            state.bot_audio_sent = True
            await _send_twilio_media(twilio_ws, state, event.get("delta"))
        elif event_type in {"response.audio.done", "response.output_audio.done"}:
            state.response_in_progress = False
            await _send_twilio_mark(twilio_ws, state)
            if await _handle_closing_response_done(openai_ws, twilio_ws, config, state):
                return
        elif event_type in {
            "response.audio_transcript.delta",
            "response.output_audio_transcript.delta",
        }:
            delta = event.get("delta")
            if delta:
                state.patient_transcript.append(delta)
        elif event_type in {
            "response.audio_transcript.done",
            "response.output_audio_transcript.done",
        }:
            transcript = event.get("transcript") or "".join(state.patient_transcript).strip()
            state.patient_transcript.clear()
            _log_utterance(state, "PATIENT", transcript)
        elif event_type == "conversation.item.input_audio_transcription.completed":
            _log_utterance(state, "AGENT", event.get("transcript", ""))
        elif event_type == "input_audio_buffer.speech_started":
            state.agent_speech_started = True
            await _handle_barge_in(openai_ws, twilio_ws, state)
        elif event_type == "response.function_call_arguments.done":
            if event.get("name") == "end_call":
                await _request_hangup_after_current_audio(
                    openai_ws,
                    twilio_ws,
                    config,
                    state,
                    "goal completed",
                )
                if state.hung_up:
                    return
        elif event_type == "response.done":
            state.response_in_progress = False
            if await _handle_closing_response_done(openai_ws, twilio_ws, config, state):
                return
        elif event_type == "error":
            error = event.get("error", {})
            print(f"OpenAI error: {error.get('message') or error}")


async def _initial_silence_fallback(openai_ws: Any, config: BridgeConfig, state: BridgeState) -> None:
    while not state.stream_sid and not config.done.is_set():
        await asyncio.sleep(0.05)
    await asyncio.sleep(INITIAL_GREETING_WAIT_SECONDS)
    if (
        not state.agent_speech_started
        and not state.initial_response_sent
        and not state.response_in_progress
        and not state.closing
        and not config.done.is_set()
    ):
        state.initial_response_sent = True
        await _create_patient_response(
            openai_ws,
            "The other side has not greeted you yet. Start the call naturally and briefly.",
        )
    await config.done.wait()


async def _max_duration_timer(
    openai_ws: Any,
    twilio_ws: WebSocket,
    config: BridgeConfig,
    state: BridgeState,
) -> None:
    await asyncio.sleep(config.scenario.max_seconds)
    if not state.closing:
        await _say_goodbye_then_hangup(openai_ws, twilio_ws, state, "max_seconds reached")
    await config.done.wait()


async def _handle_barge_in(openai_ws: Any, twilio_ws: WebSocket, state: BridgeState) -> None:
    if state.stream_sid:
        await twilio_ws.send_json({"event": "clear", "streamSid": state.stream_sid})
        state.pending_marks.clear()
    if state.response_in_progress:
        await _send_openai(openai_ws, {"type": "response.cancel"})
    state.response_in_progress = False


async def _request_hangup_after_current_audio(
    openai_ws: Any,
    twilio_ws: WebSocket,
    config: BridgeConfig,
    state: BridgeState,
    reason: str,
) -> None:
    state.closing = True
    state.close_reason = reason
    if not state.response_in_progress:
        if state.bot_audio_sent:
            await _send_twilio_mark(twilio_ws, state)
            await _finish_after_audio_flush(config, state)
        else:
            await _say_goodbye_then_hangup(openai_ws, twilio_ws, state, reason)


async def _say_goodbye_then_hangup(
    openai_ws: Any,
    twilio_ws: WebSocket,
    state: BridgeState,
    reason: str,
) -> None:
    state.closing = True
    state.goodbye_requested = True
    state.goodbye_attempts += 1
    state.close_reason = reason
    if state.response_in_progress:
        await _send_openai(openai_ws, {"type": "response.cancel"})
        if state.stream_sid:
            await twilio_ws.send_json({"event": "clear", "streamSid": state.stream_sid})
            state.pending_marks.clear()
    state.response_in_progress = True
    state.bot_audio_sent = False
    state.initial_response_sent = True
    await _create_patient_response(
        openai_ws,
        "Say a brief, warm goodbye as the patient and do not ask another question.",
    )


async def _create_patient_response(openai_ws: Any, instructions: str) -> None:
    await _send_openai(
        openai_ws,
        {
            "type": "response.create",
            "response": {
                "output_modalities": ["audio"],
                "instructions": instructions,
            },
        },
    )


async def _handle_closing_response_done(
    openai_ws: Any,
    twilio_ws: WebSocket,
    config: BridgeConfig,
    state: BridgeState,
) -> bool:
    if not state.closing:
        return False
    if state.goodbye_requested and not state.bot_audio_sent:
        if state.goodbye_attempts < MAX_GOODBYE_ATTEMPTS:
            await _say_goodbye_then_hangup(
                openai_ws,
                twilio_ws,
                state,
                state.close_reason or "closing",
            )
            return False
        await _finish_after_audio_flush(config, state)
        return True
    await _finish_after_audio_flush(config, state)
    return True


async def _finish_after_audio_flush(config: BridgeConfig, state: BridgeState) -> None:
    await _wait_for_marks(state)
    state.hangup_started = True
    await _hang_up_if_needed(config, state)
    config.done.set()


async def _wait_for_marks(state: BridgeState) -> None:
    deadline = time.monotonic() + GOODBYE_FLUSH_SECONDS
    while state.pending_marks and time.monotonic() < deadline:
        await asyncio.sleep(0.05)


async def _hang_up_call(twilio_client: Client, call_sid: str) -> None:
    await asyncio.to_thread(twilio_client.calls(call_sid).update, status="completed")
    print(f"Call ended: call_sid={call_sid}")


async def _hang_up_if_needed(config: BridgeConfig, state: BridgeState) -> None:
    if not state.call_sid or state.hung_up:
        return
    try:
        await _hang_up_call(config.twilio_client, state.call_sid)
        state.hung_up = True
    except Exception as exc:
        print(f"Failed to hang up call_sid={state.call_sid}: {exc}")


async def _send_twilio_media(twilio_ws: WebSocket, state: BridgeState, payload: str | None) -> None:
    if not payload or not state.stream_sid:
        return
    await twilio_ws.send_json(
        {
            "event": "media",
            "streamSid": state.stream_sid,
            "media": {"payload": payload},
        }
    )


async def _send_twilio_mark(twilio_ws: WebSocket, state: BridgeState) -> None:
    if not state.stream_sid or not state.bot_audio_sent:
        return
    state.mark_counter += 1
    mark_name = f"bot-audio-{state.mark_counter}"
    state.pending_marks.add(mark_name)
    await twilio_ws.send_json(
        {
            "event": "mark",
            "streamSid": state.stream_sid,
            "mark": {"name": mark_name},
        }
    )


async def _send_openai(openai_ws: Any, payload: dict[str, Any]) -> None:
    await openai_ws.send(json.dumps(payload))


def _log_utterance(state: BridgeState, speaker: str, transcript: str) -> None:
    text = " ".join((transcript or "").split())
    if text:
        print(f"[{state.elapsed()}] {speaker}: {text}")
