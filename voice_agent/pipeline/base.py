import asyncio
from typing import List

from voice_agent.components import PipelineComponent
from voice_agent.session import AgentSession
from voice_agent.events import VoiceAgentEvent
from voice_agent.frame import Frame


class Pipeline:
    def __init__(self, components: List[PipelineComponent]):
        self.components = components
        self.session = AgentSession()

        # connect components in a sequence.
        for i, comp in enumerate(self.components):
            # bind session to each component so they can emit events and subscribe to event bus
            comp.bind_session(self.session)
            
            # set downstream component for each component
            if i < len(self.components) - 1:
                comp.set_next(self.components[i+1])
                
    async def emit_event(self, event: VoiceAgentEvent):
        """emit events to external callers"""
        await self.session.emit(event)
        
    async def push_frame(self, frame: Frame):
        """向管道第一个组件注入外来数据栈"""
        if self.components:
            await self.components[0].input_queue.put(frame)
            
    async def run(self):
        """并发运行事件总线和所有流水线组件"""
        tasks = [asyncio.create_task(self.session.run())]
        for comp in self.components:
            tasks.append(asyncio.create_task(comp.run()))
            
        await asyncio.gather(*tasks)
