#!/usr/bin/env python3
"""
RemoteLLMconnector - Bridges local vLLM to remote broker via WebSocket.
Based on https://github.com/viljo/RemoteLLMconnector
"""

import asyncio
import json
import logging
import os
import sys
from typing import Optional

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

# Configuration from environment
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:8000")
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "")
BROKER_WS_URL = os.getenv("BROKER_WS_URL")
CONNECTOR_TOKEN = os.getenv("CONNECTOR_TOKEN")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-coder-30b-a3b-fp8")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Reconnection settings
INITIAL_BACKOFF = 1
MAX_BACKOFF = 60
BACKOFF_MULTIPLIER = 2


class Connector:
    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.backoff = INITIAL_BACKOFF

    async def start(self):
        """Main entry point - connects to broker and handles messages."""
        if not BROKER_WS_URL or not CONNECTOR_TOKEN:
            logger.error("BROKER_WS_URL and CONNECTOR_TOKEN must be set")
            sys.exit(1)

        self.http_client = httpx.AsyncClient(timeout=300.0)

        while True:
            try:
                await self.connect_and_serve()
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"Connection error: {e}")

            logger.info(f"Reconnecting in {self.backoff}s...")
            await asyncio.sleep(self.backoff)
            self.backoff = min(self.backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)

    async def connect_and_serve(self):
        """Establish WebSocket connection and handle incoming requests."""
        headers = {"Authorization": f"Bearer {CONNECTOR_TOKEN}"}

        logger.info(f"Connecting to broker: {BROKER_WS_URL}")
        async with websockets.connect(BROKER_WS_URL, extra_headers=headers) as ws:
            self.ws = ws
            self.backoff = INITIAL_BACKOFF  # Reset backoff on successful connection
            logger.info("Connected to broker successfully")

            # Register available models
            await self.register_models()

            # Handle incoming messages
            async for message in ws:
                asyncio.create_task(self.handle_message(message))

    async def register_models(self):
        """Send model registration to broker."""
        registration = {
            "type": "register",
            "models": [MODEL_NAME]
        }
        await self.ws.send(json.dumps(registration))
        logger.info(f"Registered model: {MODEL_NAME}")

    async def handle_message(self, message: str):
        """Process incoming request from broker."""
        try:
            request = json.loads(message)
            request_id = request.get("id")
            request_type = request.get("type")

            if request_type == "chat_completion":
                await self.handle_chat_completion(request_id, request.get("payload", {}))
            elif request_type == "models":
                await self.handle_models_request(request_id)
            elif request_type == "ping":
                await self.send_response(request_id, {"type": "pong"})
            else:
                logger.warning(f"Unknown request type: {request_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            if request_id:
                await self.send_error(request_id, str(e))

    async def handle_chat_completion(self, request_id: str, payload: dict):
        """Forward chat completion request to local vLLM."""
        url = f"{LOCAL_LLM_URL}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if LOCAL_LLM_API_KEY:
            headers["Authorization"] = f"Bearer {LOCAL_LLM_API_KEY}"

        # Check if streaming is requested
        stream = payload.get("stream", False)

        try:
            if stream:
                await self.handle_streaming_completion(request_id, url, headers, payload)
            else:
                response = await self.http_client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                await self.send_response(request_id, {
                    "type": "chat_completion_response",
                    "data": response.json()
                })
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM request failed: {e.response.status_code}")
            await self.send_error(request_id, f"LLM error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            await self.send_error(request_id, str(e))

    async def handle_streaming_completion(self, request_id: str, url: str,
                                          headers: dict, payload: dict):
        """Handle streaming chat completion with SSE."""
        async with self.http_client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        await self.send_response(request_id, {
                            "type": "stream_end"
                        })
                        break
                    else:
                        await self.send_response(request_id, {
                            "type": "stream_chunk",
                            "data": json.loads(data)
                        })

    async def handle_models_request(self, request_id: str):
        """Return available models."""
        await self.send_response(request_id, {
            "type": "models_response",
            "data": {
                "object": "list",
                "data": [{
                    "id": MODEL_NAME,
                    "object": "model",
                    "owned_by": "local"
                }]
            }
        })

    async def send_response(self, request_id: str, response: dict):
        """Send response back to broker."""
        response["id"] = request_id
        await self.ws.send(json.dumps(response))

    async def send_error(self, request_id: str, error_message: str):
        """Send error response to broker."""
        await self.send_response(request_id, {
            "type": "error",
            "error": error_message
        })


async def main():
    connector = Connector()
    await connector.start()


if __name__ == "__main__":
    asyncio.run(main())
