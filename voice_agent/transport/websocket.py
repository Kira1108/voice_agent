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
        pass
    
    
    @property
    def output(self) -> PipelineComponent:
        pass
    
    
    
class WebSocketInputComponent(BaseSourceComponent):
    
    def __init__(self, websocket: WebSocket):
        super().__init__(name="WebSocketInput")
        self.websocket = websocket
        
    async def receive_messages(self):
        try:
            while True:
                message = await self.websocket.receive()
                if "bytes" in message and message["bytes"]:
                    yield AudioFrame(audio_data=message["bytes"])
                elif "text" in message and message["text"]:
                    # We only care about audio frames passing through binary and session end for now.
                    pass
        except WebSocketDisconnect:
            yield VoiceAgentEvent(type=EventType.SESSION_ENDED)
        