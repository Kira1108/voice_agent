import pytest
import asyncio
from fastapi import WebSocketDisconnect
from voice_agent.transport.websocket import WebSocketTransport, WebSocketInputComponent, WebSocketOutputComponent
from voice_agent.frame.base import AudioFrame
from voice_agent.events.base import VoiceAgentEvent, EventType
from voice_agent.pipeline.base import Pipeline

class MockWebSocket:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.current_idx = 0
        self.sent_bytes = []
        
    async def receive(self):
        # 微小的延迟，防止立刻耗尽并且更好地模拟网络 IO
        await asyncio.sleep(0.01)
        if self.current_idx < len(self.messages):
            msg = self.messages[self.current_idx]
            self.current_idx += 1
            if isinstance(msg, Exception):
                raise msg
            return msg
        # 一旦消息用完，我们把它 block 住，真实场景下连接没断也是会阻塞在这里的
        await asyncio.sleep(3600)

    async def send_bytes(self, data: bytes):
        self.sent_bytes.append(data)

@pytest.mark.asyncio
async def test_websocket_transport_properties():
    ws = MockWebSocket()
    transport = WebSocketTransport(websocket=ws)
    
    assert isinstance(transport.input, WebSocketInputComponent)
    assert transport.input.websocket is ws
    
    assert isinstance(transport.output, WebSocketOutputComponent)
    assert transport.output.websocket is ws

@pytest.mark.asyncio
async def test_websocket_output_component():
    ws = MockWebSocket()
    output_comp = WebSocketOutputComponent(websocket=ws)
    
    frame = AudioFrame(audio_data=b"test_send_data")
    await output_comp.process_frame(frame)
    
    assert len(ws.sent_bytes) == 1
    assert ws.sent_bytes[0] == b"test_send_data"

@pytest.mark.asyncio
async def test_websocket_input_component_audio_and_disconnect():
    messages = [
        {"bytes": b"test_audio_1"},
        {"text": "this should be ignored"},
        {"type": "websocket.disconnect", "code": 1000} # 测试最新加的 dict 类型 disconnect
    ]
    
    mock_ws = MockWebSocket(messages)
    component = WebSocketInputComponent(websocket=mock_ws)
    
    results = []
    async for msg in component.receive_messages():
        results.append(msg)
        
    assert len(results) == 2
    assert isinstance(results[0], AudioFrame)
    assert results[0].audio_data == b"test_audio_1"
    
    assert isinstance(results[1], VoiceAgentEvent)
    assert results[1].type == EventType.SESSION_ENDED

@pytest.mark.asyncio
async def test_websocket_transport_echo_pipeline():
    """这是一个终极测试，把 Input 到 Output 真正拿 Pipeline 串起来跑一遍"""
    messages = [
        {"bytes": b"chunk1"},
        {"bytes": b"chunk2"},
        {"type": "websocket.disconnect", "code": 1000}
    ]
    ws = MockWebSocket(messages)
    transport = WebSocketTransport(websocket=ws)
    
    # 模拟连线：Input收到包立刻传给Output
    transport.input.to(transport.output)
    
    pipeline = Pipeline(components=[transport.input, transport.output])
    
    # 启动 Pipeline。一旦收到 websocket.disconnect，它会自动触发 SESSION_ENDED 事件，
    # 从而导致所有组件跳出循坏，并最终从 pipeline.run() 中优雅退出。
    await asyncio.wait_for(pipeline.run(), timeout=2.0)
    
    # 断言我们的 Output 组件真的收到了并发出去了两次音频块
    assert len(ws.sent_bytes) == 2
    assert ws.sent_bytes[0] == b"chunk1"
    assert ws.sent_bytes[1] == b"chunk2"

