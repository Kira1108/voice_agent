import pytest
import asyncio
from voice_agent.components.base import PipelineComponent
from voice_agent.frame.base import TextFrame # assuming this exists from previous read
from voice_agent.events import VoiceAgentEvent, EventType

class MockComponent(PipelineComponent):
    def __init__(self, name):
        super().__init__(name)
        self.processed_frames = []

    async def process_frame(self, frame):
        self.processed_frames.append(frame)
        await self.push(frame)

@pytest.mark.asyncio
async def test_pipeline_chaining():
    comp1 = MockComponent("Comp1")
    comp2 = MockComponent("Comp2")
    
    # link pipeline components
    comp1.set_next(comp2)
    assert comp1.next_component == comp2

    # Provide initial frame
    frame = TextFrame(text="test data")
    await comp1.input_queue.put(frame)

    t1 = asyncio.create_task(comp1.run())
    t2 = asyncio.create_task(comp2.run())

    # Yield control to let event loop process
    await asyncio.sleep(0.1)

    assert len(comp1.processed_frames) == 1
    assert comp1.processed_frames[0] == frame
    
    assert len(comp2.processed_frames) == 1
    assert comp2.processed_frames[0] == frame

    # stop gracefully
    comp1._stop_event.set()
    comp2._stop_event.set()
    
    await asyncio.gather(t1, t2)

@pytest.mark.asyncio
async def test_component_flush_on_cancel():
    comp = MockComponent("Comp3")
    
    for _ in range(5):
        await comp.input_queue.put(TextFrame(text="dummy frame"))
    
    assert comp.input_queue.qsize() == 5
    
    await comp.handle_event(VoiceAgentEvent(type=EventType.CANCEL_PIPELINE))
    assert comp.input_queue.qsize() == 0

@pytest.mark.asyncio
async def test_component_stop_on_session_ended():
    comp = MockComponent("Comp4")
    assert not comp._stop_event.is_set()
    
    await comp.handle_event(VoiceAgentEvent(type=EventType.SESSION_ENDED))
    assert comp._stop_event.is_set()
