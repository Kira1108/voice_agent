import asyncio
import base64
import hashlib
import hmac
import json
import os
import random
import time
import urllib.parse
from datetime import datetime, timedelta
from uuid import uuid4

import websockets

from voice_agent.components.stt import BaseSTTComponent
from voice_agent.frame import AudioFrame, TextFrame


def _generate_unique_id() -> str:
    """Generate a unique ID for voice session."""
    return base64.urlsafe_b64encode(uuid4().bytes).rstrip(b'=').decode('ascii')

def _url_encode(component: str) -> str:
    """URL encode a component."""
    return urllib.parse.quote(component)


def _generate_signature(message: str, secret_key) -> str:
    """Generate HMAC-SHA1 signature for authentication."""
    secret_key = secret_key
    hmac_obj = hmac.new(secret_key.encode(), message.encode(), hashlib.sha1)
    hmac_digest = hmac_obj.digest()
    return base64.b64encode(hmac_digest).decode('utf-8')

def _build_api_url(base_url:str, part_url:str,secret_id:str, secret_key:str,vad_silence: int = 1000) -> str:
    """Build the WebSocket API URL with authentication parameters."""
    params = [
        "engine_model_type=16k_zh_large",
        "needvad=1",
        f"timestamp={int(time.time())}",
        f"vad_silence_time={vad_silence}",
        f"secretid={secret_id}",
        f"expired={int((datetime.now() + timedelta(days=1)).timestamp())}",
        f"voice_id={_generate_unique_id()}",
        "voice_format=1",
        "noise_threshold=1",
        f"nonce={random.randint(100000, 999999)}",
    ]
    params.sort()
    
    query_string = "&".join(params)
    signature = _generate_signature(part_url + query_string, secret_key)
    encoded_signature = _url_encode(signature)
    
    return f"{base_url}{query_string}&signature={encoded_signature}"

class TencentStreamingSTT(BaseSTTComponent):
    
    def __init__(self, base_url:str, part_url:str, secret_id:str, secret_key:str, vad_silence: int = 1000):
        super().__init__(name="TencentStreamingSTT", queue_size=100)
        self._websocket_url = _build_api_url(
            base_url = base_url,
            part_url = part_url,
            secret_id= secret_id,
            secret_key= secret_key,
            vad_silence = vad_silence
        )
        self._websocket: websockets.WebSocketServerProtocol = None
        
    async def start_engine(self):
        self._websocket = await websockets.connect(self._websocket_url)
        
        auth_response = await asyncio.wait_for(self._websocket.recv(), timeout=10.0)
        auth_data = json.loads(auth_response)
        
        if auth_data.get('code') != 0:
            raise ConnectionError(f"Tencent ASR authentication failed: {auth_response}")
        
    async def send_audio(self, frame):
        if self._websocket is None:
            raise ConnectionError("WebSocket connection not established.")
        
        if isinstance(frame, AudioFrame):
            await self._websocket.send(frame.audio_data)
            
    async def receive_transcriptions(self):
        if self._websocket is None:
            raise ConnectionError("WebSocket connection not established.")
        
        try:
            while True:
                response = await self._websocket.recv()
                data = json.loads(response)
                
                # Tencent ASR puts the actual transcription inside a "result" object
                result = data.get("result", {})
                
                # slice_type == 0: streaming intermediate result
                # slice_type == 2: final transcription sentence
                if result.get('slice_type') == 2:
                    text = result.get('voice_text_str', '')
                    # print(f"[Tencent ASR] Final transcription: {text}")
                    yield TextFrame(text=text)
                elif result.get('slice_type') == 0:
                    text = result.get('voice_text_str', '')
                    print(f"  ... [Tencent ASR Intermediate]: {text}", end='\r')
                    
        except websockets.exceptions.ConnectionClosed:
            print("\nTencent ASR WebSocket connection closed.")
        except Exception as e:
            print(f"\nError in Tencent ASR receive loop: {e}")
            
    async def stop_engine(self):
        if self._websocket is not None:
            await self._websocket.close()