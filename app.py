import os
import json
import base64
import audioop
import asyncio
import threading
import queue
import numpy as np
import sounddevice as sd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import websocket  # from websocket-client
from dotenv import load_dotenv
load_dotenv()

# Debug toggles for OpenAI WebSocket
# Set OPENAI_WS_DEBUG=true to see detailed conversation flow logs
# Set OPENAI_WS_TRACE=true to see low-level websocket traffic
OPENAI_WS_TRACE = os.getenv("OPENAI_WS_TRACE", "false").lower() in ("1", "true", "yes")
OPENAI_WS_DEBUG = os.getenv("OPENAI_WS_DEBUG", "false").lower() in ("1", "true", "yes")

app = FastAPI()

# Local playback speaker: 24 kHz, mono, 16-bit
# OpenAI Realtime returns PCM16 at 24000 Hz by default
SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"

ENABLE_LOCAL_PLAYBACK = os.getenv("ENABLE_LOCAL_PLAYBACK", "true").lower() in ("1", "true", "yes")

# Create one output stream for the app lifetime if enabled
speaker: sd.OutputStream | None = None
if ENABLE_LOCAL_PLAYBACK:
    speaker = sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, blocksize=0)
    speaker.start()


def _build_instructions() -> str:
    """Build translator-style system instructions.

    Honors OPENAI_SYSTEM_PROMPT if provided; otherwise constructs a translation-only prompt
    targeting OPENAI_TRANSLATE_TO (default: English).
    """
    explicit = "You are a bilingual translator. Strictly translate all input speech and text between English and Korean. If the input is English, output Korean. If the input is Korean, output natural, idiomatic English. Do not add prefaces, commentary, or explanations. Preserve meaning, tone, names, numbers, punctuation, and formatting. If proper nouns have a well-known translation, use it. If the input mixes both languages, translate each segment into the other language so the output is fully in one language."

    if explicit:
        return explicit

    target = os.getenv("OPENAI_TRANSLATE_TO", os.getenv("TRANSLATE_TO", "English"))
    style = os.getenv("OPENAI_TRANSLATE_STYLE", os.getenv("TRANSLATE_STYLE", "natural and concise"))
    extras = os.getenv("OPENAI_TRANSLATE_EXTRAS", "")
    base = (
        f"You are a translator. Translate all user speech into {target}. "
        f"Return only the translation with no preface or commentary. "
        f"Keep the original meaning, tone, and intent. Speak {style}. "
        f"If the user already speaks {target}, rephrase to improve clarity and flow."
    )
    if extras.strip():
        base += " " + extras.strip()
    return base

class OAIClient:
    """Minimal wrapper around websocket-client running in a background thread.

    - send_json() is thread-safe; messages are queued and sent from the WS thread
    - messages from OpenAI are forwarded into an asyncio.Queue for async consumption
    """

    def __init__(self, api_key: str, model: str, loop: asyncio.AbstractEventLoop):
        self.api_key = api_key
        self.model = model
        self.loop = loop
        self.recv_q: asyncio.Queue[str | bytes] = asyncio.Queue()
        self._send_q: "queue.Queue[str]" = queue.Queue()
        self._wsapp: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._opened = threading.Event()

    def start(self):
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        headers = [
            "Authorization: Bearer " + self.api_key,
            "OpenAI-Beta: realtime=v1",
        ]

        if OPENAI_WS_TRACE:
            # Enable very verbose websocket-client trace logs
            websocket.enableTrace(True)

        print(f"[OAI] Connecting to {url}")

        def on_open(wsapp: websocket.WebSocketApp):
            print("[OAI] WebSocket open")
            self._opened.set()

            def sender():
                while True:
                    msg = self._send_q.get()
                    if msg is None:
                        break
                    try:
                        if OPENAI_WS_DEBUG:
                            try:
                                payload = json.loads(msg)
                                t = payload.get("type")
                                print(f"[OAI] >> {t}")
                            except Exception:
                                pass
                        wsapp.send(msg)
                    except Exception:
                        break

            threading.Thread(target=sender, daemon=True).start()

        def on_message(wsapp: websocket.WebSocketApp, message):
            # message may be str (text) or bytes
            if OPENAI_WS_DEBUG and isinstance(message, (str, bytes)):
                try:
                    if isinstance(message, str):
                        mt = json.loads(message).get("type")
                        print(f"[OAI] << {mt}")
                    else:
                        print(f"[OAI] << <{len(message)} bytes>")
                except Exception:
                    pass
            self.loop.call_soon_threadsafe(self.recv_q.put_nowait, message)

        def on_error(wsapp: websocket.WebSocketApp, error):
            print(f"[OAI] error: {error}")
            self.loop.call_soon_threadsafe(self.recv_q.put_nowait, json.dumps({"type": "error", "error": str(error)}))

        def on_close(wsapp: websocket.WebSocketApp, status_code, msg):
            print(f"[OAI] closed: code={status_code} reason={msg}")
            self.loop.call_soon_threadsafe(self.recv_q.put_nowait, json.dumps({"type": "closed", "code": status_code, "reason": msg or ""}))

        def on_ping(wsapp: websocket.WebSocketApp, message):
            if OPENAI_WS_DEBUG:
                print("[OAI] <ping>")

        def on_pong(wsapp: websocket.WebSocketApp, message):
            if OPENAI_WS_DEBUG:
                print("[OAI] <pong>")

        self._wsapp = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_ping=on_ping,
            on_pong=on_pong,
        )

        def run():
            # run_forever handles SSL internally. Ensure ping_interval > ping_timeout.
            self._wsapp.run_forever(ping_interval=30, ping_timeout=10)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def send_json(self, payload: dict):
        self._send_q.put(json.dumps(payload))

    async def wait_open(self, timeout: float = 10.0) -> bool:
        """Wait until the WS is open or timeout."""
        start = self.loop.time()
        while not self._opened.is_set():
            if self.loop.time() - start >= timeout:
                return False
            await asyncio.sleep(0.05)
        return True

    def close(self):
        # stop sender and close socket
        self._send_q.put(None)  # type: ignore
        if self._wsapp is not None:
            try:
                self._wsapp.close()
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)


class TwilioMediaStreamSender:
    """Convert OpenAI 24 kHz PCM to 8 kHz μ-law and stream back to Twilio."""

    FRAME_SAMPLES = 160  # 20 ms of audio at 8 kHz

    def __init__(self, ws: WebSocket, stream_sid: str):
        self.ws = ws
        self.stream_sid = stream_sid
        self._rate_state = None
        self._buffer = bytearray()
        self._closed = False

    async def send_pcm24(self, pcm24: bytes):
        if self._closed or not pcm24:
            return
        pcm8k, self._rate_state = audioop.ratecv(pcm24, 2, 1, 24000, 8000, self._rate_state)
        if pcm8k:
            self._buffer.extend(pcm8k)
            await self._flush_full_frames()

    async def flush(self, pad: bool = False):
        if self._closed:
            self._buffer.clear()
            return
        frame_bytes = self.FRAME_SAMPLES * 2
        if pad and self._buffer:
            remainder = len(self._buffer) % frame_bytes
            if remainder:
                self._buffer.extend(b"\x00" * (frame_bytes - remainder))
        await self._flush_full_frames()
        self._buffer.clear()

    def mark_closed(self):
        self._closed = True
        self._buffer.clear()

    async def _flush_full_frames(self):
        frame_bytes = self.FRAME_SAMPLES * 2
        while len(self._buffer) >= frame_bytes and not self._closed:
            frame = bytes(self._buffer[:frame_bytes])
            del self._buffer[:frame_bytes]
            mulaw = audioop.lin2ulaw(frame, 2)
            payload = base64.b64encode(mulaw).decode()
            message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": payload},
            }
            try:
                await self.ws.send_text(json.dumps(message))
            except Exception as exc:
                self._closed = True
                print(f"Error sending Twilio media frame: {exc}")
                break


async def _oai_receiver(
    oai_client: OAIClient,
    speaking_event: asyncio.Event | None = None,
    twilio_sender: TwilioMediaStreamSender | None = None,
):
    """Receive audio from OpenAI, optionally play locally, and stream back to Twilio."""
    frames = 0
    conversation_state = {
        "user_speaking": False,
        "assistant_speaking": False,
        "response_in_progress": False,
        "session_ready": False
    }

    async def handle_assistant_audio(pcm24: bytes):
        nonlocal frames
        if not pcm24:
            return
        if ENABLE_LOCAL_PLAYBACK and speaker is not None:
            samples = np.frombuffer(pcm24, dtype=np.int16)
            speaker.write(samples)
        if twilio_sender is not None:
            await twilio_sender.send_pcm24(pcm24)
        frames += 1
        if OPENAI_WS_DEBUG and frames % 20 == 0:
            print(f"[OAI] handled audio frames: {frames}")

    while True:
        msg = await oai_client.recv_q.get()
        if isinstance(msg, bytes):
            # If raw bytes are delivered, assume PCM16 at 24000 Hz
            await handle_assistant_audio(msg)
            continue

        try:
            data = json.loads(msg)
        except Exception:
            # Unexpected payload; ignore
            continue

        event_type = data.get("type") or data.get("event")

        # Handle session lifecycle events
        if event_type == "session.created":
            conversation_state["session_ready"] = True
            if OPENAI_WS_DEBUG:
                print("[OAI] Session created and ready")

        elif event_type == "session.updated":
            if OPENAI_WS_DEBUG:
                print("[OAI] Session configuration updated")

        # Handle speech detection events
        elif event_type == "input_audio_buffer.speech_started":
            conversation_state["user_speaking"] = True
            if OPENAI_WS_DEBUG:
                print("[OAI] User started speaking")

        elif event_type == "input_audio_buffer.speech_stopped":
            conversation_state["user_speaking"] = False
            if OPENAI_WS_DEBUG:
                print("[OAI] User stopped speaking")

        elif event_type == "input_audio_buffer.committed":
            if OPENAI_WS_DEBUG:
                print("[OAI] Audio buffer committed")

        # Handle response lifecycle events
        elif event_type == "response.created":
            conversation_state["response_in_progress"] = True
            if OPENAI_WS_DEBUG:
                print("[OAI] Response generation started")

        elif event_type == "response.done":
            conversation_state["response_in_progress"] = False
            conversation_state["assistant_speaking"] = False
            if speaking_event is not None:
                speaking_event.clear()
            if OPENAI_WS_DEBUG:
                print("[OAI] Response completed - ready for next input")

        # Handle audio output events
        elif event_type == "response.output_item.added":
            if OPENAI_WS_DEBUG:
                print("[OAI] Audio output item added")

        elif event_type in ("response.audio.delta", "response.output_audio.delta"):
            # Audio content from assistant
            audio_b64 = data.get("delta")
            if audio_b64:
                try:
                    pcm24 = base64.b64decode(audio_b64)
                    await handle_assistant_audio(pcm24)
                    conversation_state["assistant_speaking"] = True
                    if speaking_event is not None:
                        speaking_event.set()
                except Exception as e:
                    if OPENAI_WS_DEBUG:
                        print(f"[OAI] Error decoding audio: {e}")

        elif event_type in ("response.audio.done", "response.output_audio.done"):
            conversation_state["assistant_speaking"] = False
            if speaking_event is not None:
                speaking_event.clear()
            if twilio_sender is not None:
                await twilio_sender.flush(pad=True)
            if OPENAI_WS_DEBUG:
                print("[OAI] Audio generation completed")

        # Handle errors
        elif event_type == "error":
            error_msg = data.get("error", {})
            print(f"[OAI] Error: {error_msg}")

        # Log conversation events for debugging
        elif event_type.startswith(("conversation.", "rate_limits.")):
            if OPENAI_WS_DEBUG:
                print(f"[OAI] {event_type}: {json.dumps(data)[:200]}")

        # Log other important events
        elif event_type not in ("response.audio.delta", "response.output_audio.delta", "input_audio_buffer.append"):
            if OPENAI_WS_DEBUG:
                print(f"[OAI] {event_type}: {json.dumps(data)[:300]}")

        # Store conversation state for debugging
        if OPENAI_WS_DEBUG and event_type in [
            "input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped",
            "response.created", "response.done"
        ]:
            print(f"[OAI] Conversation state: {conversation_state}")


async def _oai_sender(oai_client: OAIClient, pcm16_8k_queue: "asyncio.Queue[bytes]"):
    """Read PCM16 8k audio from queue, resample to 24k, and send to OpenAI."""
    rate_state = None
    while True:
        chunk8k = await pcm16_8k_queue.get()
        if chunk8k is None:
            break
        # Resample 8k -> 24k
        chunk24k, rate_state = audioop.ratecv(chunk8k, 2, 1, 8000, 24000, rate_state)
        b64 = base64.b64encode(chunk24k).decode()
        # Send as an input buffer append event (audio format configured in session)
        payload = {"type": "input_audio_buffer.append", "audio": b64}
        oai_client.send_json(payload)


async def _handle_interruption(oai_client: OAIClient):
    """Handle user interruption during assistant response."""
    try:
        # Cancel the current response
        oai_client.send_json({"type": "response.cancel"})
        if OPENAI_WS_DEBUG:
            print("[OAI] >> response.cancel (interruption)")
    except Exception as e:
        if OPENAI_WS_DEBUG:
            print(f"[OAI] Error cancelling response: {e}")


@app.websocket("/audio")
async def audio_ws(ws: WebSocket):
    """Twilio <-> OpenAI Realtime bridge.

    - Receives Twilio Media Stream events with 8k μ-law audio
    - Streams audio to OpenAI Realtime (as 24k PCM16)
    - Streams OpenAI audio responses back to Twilio (as 8k μ-law)
    """
    await ws.accept()
    print("Twilio connected")

    # OpenAI realtime connection and tasks
    oai_client: OAIClient | None = None
    oai_recv_task: asyncio.Task | None = None
    oai_send_task: asyncio.Task | None = None
    pcm16_queue: asyncio.Queue[bytes] = asyncio.Queue()
    speaking = asyncio.Event()  # True while OpenAI is speaking
    twilio_sender: TwilioMediaStreamSender | None = None

    stream_sid = None
    instructions = _build_instructions()
    voice = os.getenv("OPENAI_VOICE", "verse")
    # Rely on server-side VAD; no local thresholds required.

    frame_count = 0
    try:
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue

            event = data.get("event")
            if event == "start":
                fmt = data.get("start", {}).get("mediaFormat")
                stream_sid = data.get("start", {}).get("streamSid")
                print(f"Stream started (sid={stream_sid}) format={fmt}")

                # Connect to OpenAI Realtime now that we have an active Twilio stream
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise RuntimeError("OPENAI_API_KEY not set")
                model = os.getenv("OPENAI_MODEL", "gpt-4o-realtime-preview-2024-12-17")
                oai_client = OAIClient(api_key, model, asyncio.get_event_loop())
                oai_client.start()
                # Wait for the socket to open to catch early failures
                ok = await oai_client.wait_open(10.0)
                if not ok:
                    print("[OAI] Failed to open WebSocket within timeout")
                    raise RuntimeError("OpenAI Realtime WebSocket failed to open")

                # Configure session defaults per docs BEFORE streaming audio
                try:
                    print(f"[OAI] applying instructions: {instructions[:160]}{'...' if len(instructions)>160 else ''}")
                    oai_client.send_json(
                        {
                            "type": "session.update",
                            "session": {
                                "type": "realtime",
                                "output_modalities": ["audio"],
                                "audio": {
                                    "input": {
                                        "format": {"type": "audio/pcm", "rate": 24000},
                                        "turn_detection": {"type": "semantic_vad"}
                                    },
                                    "output": {
                                        "format": {"type": "audio/pcm"},
                                        "voice": voice,
                                    },
                                },
                                "instructions": instructions,
                            },
                        }
                    )
                    if OPENAI_WS_DEBUG:
                        print("[OAI] >> session.update (server VAD, voice, formats)")
                    oai_client.send_json(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "system",
                                "content": [
                                    {"type": "input_text", "text": instructions}
                                ],
                            },
                        }
                    )
                    if OPENAI_WS_DEBUG:
                        print("[OAI] >> conversation.item.create (system instructions)")
                except Exception as e:
                    print(f"session.update failed: {e}")

                if stream_sid:
                    twilio_sender = TwilioMediaStreamSender(ws, stream_sid)

                # Start receiver to play OpenAI audio locally and track speaking state
                oai_recv_task = asyncio.create_task(_oai_receiver(oai_client, speaking, twilio_sender))
                # Start sender to forward Twilio audio to OpenAI
                oai_send_task = asyncio.create_task(_oai_sender(oai_client, pcm16_queue))

            elif event == "media":
                payload_b64 = data.get("media", {}).get("payload")
                if not payload_b64:
                    continue
                # Base64 -> mu-law bytes
                mu = base64.b64decode(payload_b64)
                # μ-law -> 16-bit PCM (width=2 bytes/sample) at 8k
                pcm16_8k = audioop.ulaw2lin(mu, 2)
                # Feed to OpenAI sender task
                await pcm16_queue.put(pcm16_8k)

                # Debug: print every 50 frames received
                frame_count += 1
                if frame_count % 50 == 0:
                    print(f"Received media frames: {frame_count}")

                # Server-side VAD automatically handles:
                # 1. Speech detection (input_audio_buffer.speech_started)
                # 2. Silence detection (input_audio_buffer.speech_stopped)
                # 3. Buffer commit and response generation
                # 4. Conversation turn management
                # No manual intervention needed for basic conversation flow

            elif event == "stop":
                print("Stream stopped")
                if twilio_sender is not None:
                    try:
                        await twilio_sender.flush(pad=True)
                    except Exception as exc:
                        if OPENAI_WS_DEBUG:
                            print(f"[Twilio] flush on stop failed: {exc}")
                break

    except WebSocketDisconnect:
        print("WS disconnected")
    finally:
        # Signal sender to stop
        try:
            await pcm16_queue.put(None)  # type: ignore
        except Exception:
            pass
        # Cancel tasks
        for t in (oai_recv_task, oai_send_task):
            if t:
                t.cancel()
        # Close OpenAI socket
        try:
            if oai_client:
                oai_client.close()
        except Exception:
            pass
        if twilio_sender is not None:
            try:
                await twilio_sender.flush(pad=False)
            except Exception:
                pass
            twilio_sender.mark_closed()
        # Keep speaker open for reuse; if you want, stop/close here.
        pass
