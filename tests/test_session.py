import pytest
import asyncio
from voice_agent.components.base import PipelineComponent
from voice_agent.events import VoiceAgentEvent, EventType
from voice_agent.session.agent_session import AgentSession
from voice_agent.frame import Frame

class MockSessionComponent(PipelineComponent):
    def __init__(self, name):
        super().__init__(name)
        self.handled_events = []

    async def process_frame(self, frame: Frame):
        pass

    async def handle_event(self, event: VoiceAgentEvent):
        self.handled_events.append(event)
        await super().handle_event(event)

@pytest.mark.asyncio
async def test_session_registration_and_broadcasting():
    session = AgentSession()
    comp = MockSessionComponent("MockComp")
    
    # bind_session implicitly calls session.register_component()
    comp.bind_session(session)
    
    assert comp.session == session
    assert comp in session.subscriptions[EventType.USER_STARTED_SPEAKING]
    assert comp in session.subscriptions[EventType.SESSION_ENDED]
    
    # Run the session loop in background
    run_task = asyncio.create_task(session.run())
    
    # Provide an event to process normally
    test_event = VoiceAgentEvent(type=EventType.USER_STARTED_SPEAKING, data={"foo": "bar"})
    await session.put_event(test_event)
    
    # sleep slightly to allow event loop to pick it up in `run_task`
    await asyncio.sleep(0.1)
    
    assert len(comp.handled_events) == 1
    assert comp.handled_events[0] == test_event
    assert not comp._stop_event.is_set()

    # provide SESSION_ENDED and wait for the run_task to gracefully finish
    end_event = VoiceAgentEvent(type=EventType.SESSION_ENDED)
    await session.put_event(end_event)
    
    await run_task
    
    assert len(comp.handled_events) == 2
    assert comp.handled_events[-1] == end_event
    
    # PipelineComponent base implementation of `handle_event` calls `_stop_event.set()`
    # on EventType.SESSION_ENDED
    assert comp._stop_event.is_set()
