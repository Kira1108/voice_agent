import pytest
import asyncio
from voice_agent.components.stt import BaseSTTComponent
from voice_agent.components.base import PipelineComponent
from voice_agent.frame import AudioFrame, TextFrame
from voice_agent.events import VoiceAgentEvent, EventType
from voice_agent.pipeline.base import Pipeline

class MockSTTComponent(BaseSTTComponent):
    def __init__(self):
        super().__init__(name="MockSTT")
        self.sent_audio = []
        self.started = False
        self.stopped = False

    async def start_engine(self):
        self.started = True

    async def send_audio(self, frame: AudioFrame):
        self.sent_audio.append(frame.audio_data)

    async def receive_transcriptions(self):
        # yields two text frames then exits
        await asyncio.sleep(0.01)
        yield TextFrame("hello")
        await asyncio.sleep(0.01)
        yield TextFrame("world")
        
    async def stop_engine(self):
        self.stopped = True

class MockSinkComponent(PipelineComponent):
    def __init__(self):
        super().__init__(name="Sink")
        self.received_frames = []
        
    async def process_frame(self, frame):
        self.received_frames.append(frame)

@pytest.mark.asyncio
async def test_stt_base_component_lifecycle():
    stt = MockSTTComponent()
    sink = MockSinkComponent()
    
    stt.to(sink)
    pipeline = Pipeline(components=[stt, sink])
    
    run_task = asyncio.create_task(pipeline.run())
    await asyncio.sleep(0.05) # let the receive generator yield its texts
    
    # 1. Assert start engine called
    assert stt.started is True
    
    # Send some audio
    await stt.input_queue.put(AudioFrame(audio_data=b"mock1"))
    await asyncio.sleep(0.01)
    
    # 2. Assert process_frame passes audio downstream
    assert len(stt.sent_audio) == 1
    assert stt.sent_audio[0] == b"mock1"
    
    # Wait for the async generator to hit sink
    await asyncio.sleep(0.05)
    
    # 3. Assert TextFrames received from STT generator were pushed to downstream sink
    assert len(sink.received_frames) == 2
    assert sink.received_frames[0].text == "hello"
    assert sink.received_frames[1].text == "world"
    
    # Send stop signal to tear down
    await pipeline.stop()
    await asyncio.wait_for(run_task, timeout=1.0)
    
    # 4. Assert stop engine called
    assert stt.stopped is True
