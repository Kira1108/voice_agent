from __future__ import annotations
from dataclasses import dataclass
from fastapi import WebSocket, WebSocketDisconnect
from voice_agent.components.base import BaseSourceComponent, PipelineComponent
from voice_agent.frame import AudioFrame
from voice_agent.events import VoiceAgentEvent, EventType

class WebSocketTransport:
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._input = WebSocketInputComponent(websocket=self.websocket)
        self._output = WebSocketOutputComponent(websocket=self.websocket)
        
    @property
    def input(self) -> BaseSourceComponent:
        return self._input
    
    @property
    def output(self) -> PipelineComponent:
        return self._output
    
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
            try:
                await self.websocket.send_bytes(frame.audio_data)
            except RuntimeError as e:
                if "close" in str(e).lower() or "disconnected" in str(e).lower():
                    pass # Ignore if the socket has already been closed
                else:
                    raise e
            except Exception as e:
                print(f"[WebSocketOutput] encountered an error: {e}")