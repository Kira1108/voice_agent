import pytest
import asyncio
from voice_agent.pipeline.base import Pipeline
from voice_agent.components.base import PipelineComponent
from voice_agent.frame.base import TextFrame

class MockSourceComponent(PipelineComponent):
    async def process_frame(self, frame):
        await self.push(frame)

class MockSinkComponent(PipelineComponent):
    def __init__(self, name: str):
        super().__init__(name)
        self.processed_frames = 0
        
    async def process_frame(self, frame):
        self.processed_frames += 1

@pytest.mark.asyncio
async def test_pipeline_run_and_stop():
    source = MockSourceComponent("source")
    sink = MockSinkComponent("sink")
    
    source.to(sink)
    
    pipeline = Pipeline(components=[source, sink])
    
    # Run pipeline in a background task
    run_task = asyncio.create_task(pipeline.run())
    
    # Yield control to let the pipeline initialize the session and component loops
    await asyncio.sleep(0.01)
    
    # Verify bindings
    assert pipeline.session is not None
    assert source.session is pipeline.session
    assert sink.session is pipeline.session
    
    # Push a frame into the source
    await source.input_queue.put(TextFrame(text="hello"))
    
    # Yield control to let the frames propagate
    await asyncio.sleep(0.01)
    
    # Verify processing
    assert sink.processed_frames == 1
    
    # Stop the pipeline gracefully
    await pipeline.stop()
    
    # Ensure run task exits cleanly within a reasonable timeout
    await asyncio.wait_for(run_task, timeout=1.0)
    
    # Check that component stop events were triggered
    assert source._stop_event.is_set()
    assert sink._stop_event.is_set()
