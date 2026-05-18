import asyncio
from typing import List

from voice_agent.components.base import PipelineComponent
from voice_agent.session.agent_session import AgentSession
from voice_agent.events.base import VoiceAgentEvent, EventType

class Pipeline:
    def __init__(self, components: List[PipelineComponent] = None):
        self.components = components or []
        self.session = None

    def register_components(self, *components: PipelineComponent):
        """Register components to the pipeline."""
        self.components.extend(components)

    def _prepare(self):
        """Set up the session and bind it to all components."""
        self.session = AgentSession()
        for comp in self.components:
            comp.bind_session(self.session)

    async def run(self):
        """Prepare the pipeline, start all components and the session loop, and wait for graceful termination."""
        self._prepare()
        
        # Start all component loops
        component_tasks = [asyncio.create_task(comp.run()) for comp in self.components]
        
        # Start the session event loop
        session_task = asyncio.create_task(self.session.run())
        
        # Wait until all components stop running (triggered by SESSION_ENDED event)
        await asyncio.gather(*component_tasks)
        
        # Cancel the session task once all components gracefully stop
        session_task.cancel()
        try:
            await session_task
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """Gracefully terminate the pipeline by injecting a SESSION_ENDED event."""
        if self.session:
            await self.session.put_event(VoiceAgentEvent(type=EventType.SESSION_ENDED))
