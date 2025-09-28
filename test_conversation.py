#!/usr/bin/env python3
"""
Simple test script to verify the OpenAI Realtime API conversation flow works correctly.

This script helps debug conversation issues by:
1. Connecting directly to OpenAI Realtime API
2. Sending test audio or text inputs
3. Monitoring conversation lifecycle events
4. Verifying multiple turns work properly

Usage:
    python test_conversation.py

Environment variables required:
    OPENAI_API_KEY=your_openai_api_key
    OPENAI_WS_DEBUG=true  (optional, for detailed logs)
"""

import os
import json
import base64
import asyncio
import threading
import queue
import websocket
from dotenv import load_dotenv

load_dotenv()

# Enable debug logging
OPENAI_WS_DEBUG = True

class TestOAIClient:
    """Simplified OpenAI Realtime client for testing conversation flow."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.recv_q = asyncio.Queue()
        self._send_q = queue.Queue()
        self._wsapp = None
        self._thread = None
        self._opened = threading.Event()
        self.conversation_state = {
            "session_ready": False,
            "user_speaking": False,
            "assistant_speaking": False,
            "response_in_progress": False,
            "conversation_items": []
        }

    def start(self):
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        headers = [
            "Authorization: Bearer " + self.api_key,
            "OpenAI-Beta: realtime=v1",
        ]

        def on_open(wsapp):
            print("[TEST] WebSocket connected to OpenAI")
            self._opened.set()

        def on_message(wsapp, message):
            asyncio.get_event_loop().call_soon_threadsafe(self.recv_q.put_nowait, message)

        def on_error(wsapp, error):
            print(f"[TEST] WebSocket error: {error}")

        def on_close(wsapp, status_code, msg):
            print(f"[TEST] WebSocket closed: {status_code} - {msg}")

        self._wsapp = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        def run():
            self._wsapp.run_forever()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def send_json(self, payload):
        if self._wsapp:
            self._wsapp.send(json.dumps(payload))
            if OPENAI_WS_DEBUG:
                print(f"[TEST] >> {payload.get('type')}")

    async def wait_open(self, timeout=10.0):
        start = asyncio.get_event_loop().time()
        while not self._opened.is_set():
            if asyncio.get_event_loop().time() - start >= timeout:
                return False
            await asyncio.sleep(0.1)
        return True

    def close(self):
        if self._wsapp:
            self._wsapp.close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

async def test_conversation_flow():
    """Test multi-turn conversation with OpenAI Realtime API."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    model = "gpt-4o-realtime-preview-2024-12-17"
    client = TestOAIClient(api_key, model)

    try:
        # Connect to OpenAI
        print("[TEST] Connecting to OpenAI Realtime API...")
        client.start()

        if not await client.wait_open():
            print("[TEST] Failed to connect within timeout")
            return False

        # Configure session for text conversation (easier to test)
        session_config = {
            "type": "session.update",
            "session": {
                "model": model,
                "modalities": ["text"],
                "instructions": "You are a helpful assistant. Keep responses brief for testing.",
                "voice": "verse",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 200
                },
                "tool_choice": "auto",
                "temperature": 0.8,
                "max_response_output_tokens": 100
            }
        }

        client.send_json(session_config)
        print("[TEST] Session configured")

        # Test conversation turns
        test_messages = [
            "Hello, can you hear me?",
            "What's 2 + 2?",
            "Tell me a short joke",
            "Thank you, goodbye!"
        ]

        for i, message in enumerate(test_messages, 1):
            print(f"\n[TEST] === Turn {i}: Testing message: '{message}' ===")

            # Send user message
            client.send_json({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": message}]
                }
            })

            # Request response
            client.send_json({
                "type": "response.create",
                "response": {"modalities": ["text"]}
            })

            # Wait for response completion
            response_complete = False
            timeout_count = 0
            max_timeout = 50  # 5 seconds

            while not response_complete and timeout_count < max_timeout:
                try:
                    msg = await asyncio.wait_for(client.recv_q.get(), timeout=0.1)
                    data = json.loads(msg)
                    event_type = data.get("type")

                    if OPENAI_WS_DEBUG:
                        if event_type not in ["input_audio_buffer.append"]:
                            print(f"[TEST] << {event_type}")

                    if event_type == "response.done":
                        response_complete = True
                        output_items = data.get("response", {}).get("output", [])
                        if output_items:
                            for item in output_items:
                                if item.get("type") == "message":
                                    content = item.get("content", [])
                                    for c in content:
                                        if c.get("type") == "text":
                                            print(f"[TEST] Assistant: {c.get('text')}")
                        else:
                            print("[TEST] No output in response")

                    elif event_type == "error":
                        print(f"[TEST] Error: {data}")
                        return False

                except asyncio.TimeoutError:
                    timeout_count += 1
                    continue

            if not response_complete:
                print(f"[TEST] FAILED: No response received for message {i}")
                return False

            print(f"[TEST] Turn {i} completed successfully")

            # Small delay between turns
            await asyncio.sleep(0.5)

        print("\n[TEST] ✅ All conversation turns completed successfully!")
        print("[TEST] The conversation flow is working properly.")
        return True

    except Exception as e:
        print(f"[TEST] Error during test: {e}")
        return False
    finally:
        client.close()

async def main():
    print("OpenAI Realtime API Conversation Flow Test")
    print("=" * 50)

    success = await test_conversation_flow()

    if success:
        print("\n✅ Test PASSED: Conversation flow is working correctly")
        print("Your app.py should now handle multiple conversation turns properly")
    else:
        print("\n❌ Test FAILED: There are still issues with conversation flow")
        print("Check your OpenAI API key and connection")

if __name__ == "__main__":
    asyncio.run(main())