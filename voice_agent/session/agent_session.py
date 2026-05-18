import asyncio
from typing import List, Optional, TYPE_CHECKING
from voice_agent.events import VoiceAgentEvent, EventType

if TYPE_CHECKING:
    from voice_agent.components.base import PipelineComponent

class AgentSession:
    def __init__(self):
        self.event_queue: asyncio.Queue = asyncio.Queue()
        
        # subscriptions: dict mapping event types to sets of subscribed components; allows efficient event broadcasting
        self.subscriptions: dict[EventType, set['PipelineComponent']] = {
            e: set() for e in EventType
        }
    
    def register_component(
        self, 
        component: 'PipelineComponent', 
        event_types: Optional[List[EventType]] = None):
        
        if event_types:
            for et in event_types:
                self.subscriptions[et].add(component)
        else:
            # subcribe to all events by default if no specific types are provided
            for et in EventType:
                self.subscriptions[et].add(component)
        
    async def put_event(self, event: VoiceAgentEvent):
        await self.event_queue.put(event)
        
    async def _broadcast(self, event: VoiceAgentEvent):
        components = self.subscriptions.get(event.type, set())
        if not components:
            return
            
        tasks = [component.handle_event(event) for component in components]
        # return_exceptions=True 防止某个组件的错误导致整个事件总线崩溃
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 抛出或记录异常（防止被静默吞并）
        for comp, res in zip(components, results):
            if isinstance(res, Exception):
                print(f"[{getattr(comp, 'name', 'Unknown')}] event handling error: {res}")
    
    async def run(self):
        while True:
            event = await self.event_queue.get()
            await self._broadcast(event)
            self.event_queue.task_done()
            
            # 当接收到结束事件时跳出循环
            if event.type == EventType.SESSION_ENDED:
                break