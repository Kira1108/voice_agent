from __future__ import annotations
from dataclasses import dataclass
from fastapi import WebSocket, WebSocketDisconnect
from voice_agent.components.base import BaseSourceComponent, PipelineComponent
from voice_agent.frame import AudioFrame
from voice_agent.events import VoiceAgentEvent, EventType

class WebSocketTransport:
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        
    @property
    def input(self) -> BaseSourceComponent:
        return WebSocketInputComponent(websocket=self.websocket)
    
    
    @property
    def output(self) -> PipelineComponent:
        return WebSocketOutputComponent(websocket=self.websocket)
    
class WebSocketInputComponent(BaseSourceComponent):
    
    def __init__(self, websocket: WebSocket):
        super().__init__(name="WebSocketInput")
        self.websocket = websocket
        
    async def receive_messages(self):
        try:
            while True:
                # Alternatively check client_state but catching message type/RuntimeError is safer
                message = await self.websocket.receive()
                
                if message.get("type") == "websocket.disconnect":
                    yield VoiceAgentEvent(type=EventType.SESSION_ENDED)
                    break
                elif "bytes" in message and message["bytes"]:
                    yield AudioFrame(audio_data=message["bytes"])
                elif "text" in message and message["text"]:
                    # We only care about audio frames passing through binary and session end for now.
                    pass
        except WebSocketDisconnect:
            yield VoiceAgentEvent(type=EventType.SESSION_ENDED)
        except RuntimeError as e:
            if "disconnect" in str(e).lower():
                yield VoiceAgentEvent(type=EventType.SESSION_ENDED)
            else:
                raise
        

        
class WebSocketOutputComponent(PipelineComponent):
    
    def __init__(self, websocket: WebSocket):
        super().__init__(name="WebSocketOutput")
        self.websocket = websocket
        
    async def process_frame(self, frame):
        if isinstance(frame, AudioFrame):
            await self.websocket.send_bytes(frame.audio_data)
        if isinstance(frame, AudioFrame):
            await self.websocket.send_bytes(frame.audio_data)