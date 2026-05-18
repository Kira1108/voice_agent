import pytest
import asyncio
from fastapi import WebSocketDisconnect
from voice_agent.transport.websocket import WebSocketInputComponent
from voice_agent.frame.base import AudioFrame
from voice_agent.events.base import VoiceAgentEvent, EventType

class MockWebSocket:
    def __init__(self, messages):
        self.messages = messages
        self.current_idx = 0
        
    async def receive(self):
        if self.current_idx < len(self.messages):
            msg = self.messages[self.current_idx]
            self.current_idx += 1
            if isinstance(msg, Exception):
                raise msg
            return msg
        # Default behavior if we run out of messages: just disconnect
        raise WebSocketDisconnect(code=1000)

@pytest.mark.asyncio
async def test_websocket_input_component_audio_and_disconnect():
    messages = [
        {"bytes": b"test_audio_1"},
        {"text": "this should be ignored"},
        {"bytes": b"test_audio_2"},
        WebSocketDisconnect(code=1000)
    ]
    
    mock_ws = MockWebSocket(messages)
    # We can pass our MockWebSocket because Python uses duck typing
    component = WebSocketInputComponent(websocket=mock_ws)
    
    results = []
    async for msg in component.receive_messages():
        results.append(msg)
        
    # We expect 3 results: AudioFrame, AudioFrame, and SESSION_ENDED event
    assert len(results) == 3
    
    assert isinstance(results[0], AudioFrame)
    assert results[0].audio_data == b"test_audio_1"
    
    assert isinstance(results[1], AudioFrame)
    assert results[1].audio_data == b"test_audio_2"
    
    assert isinstance(results[2], VoiceAgentEvent)
    assert results[2].type == EventType.SESSION_ENDED
