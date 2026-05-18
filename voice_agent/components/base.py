import asyncio
from typing import Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from voice_agent.events import VoiceAgentEvent, EventType
from voice_agent.frame import Frame

if TYPE_CHECKING:
    from voice_agent.session.agent_session import AgentSession


class PipelineComponent(ABC):
    
    def __init__(self, name: str, queue_size: int = 100):
        self.name = name
        # each component maintains its own input queue and process frames independently
        self.input_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.session: Optional["AgentSession"] = None
        self.next_component: Optional['PipelineComponent'] = None
        self._stop_event: asyncio.Event = asyncio.Event()
    
    def set_next(self, next_comp: 'PipelineComponent') -> 'PipelineComponent':
        """set next component in the pipeline and return it for chaining"""
        self.next_component = next_comp
        return next_comp
        
    def bind_session(self, session: "AgentSession"):
        """bind pipeline component to an agent session, allowing it to emit events and subscribe to event bus"""
        self.session = session
        self.session.register_component(self)
        
    async def push(self, frame: Frame):
        """push a frame to the next component in the pipeline"""
        if self.next_component:
            await self.next_component.input_queue.put(frame)
            
    async def emit(self, event: VoiceAgentEvent):
        """emit an event to the session's event bus"""
        if self.session:
            await self.session.put_event(event)
            
    def flush_queue(self):
        """clear all pending frames in the input queue, typically used when pipeline is interrupted or reset"""
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
                self.input_queue.task_done()
            except asyncio.QueueEmpty:
                break
            
    async def handle_event(self, event: VoiceAgentEvent):
        """handle events emitted by the session"""
        if event.type == EventType.CANCEL_PIPELINE:
            self.flush_queue()
            
        elif event.type == EventType.SESSION_ENDED:
            self._stop_event.set()
        
    @abstractmethod
    async def process_frame(self, frame: Frame):
        """process a single frame of data; must be implemented by subclasses"""
        pass
    
    async def run(self):
        get_task = None
        # create a stop task to listen for the stop event, which can be triggered by external events 
        # (like SESSION_ENDED) or internal logic (like CANCEL_PIPELINE)
        stop_task = asyncio.create_task(self._stop_event.wait())
        
        # main loop: wait for new frames or stop signal
        while not self._stop_event.is_set():
            if get_task is None:
                get_task = asyncio.create_task(self.input_queue.get())
            
            # wait for either a new frame or a stop signal
            done, pending = await asyncio.wait(
                [get_task, stop_task], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # if new frame is received, process it
            if get_task in done:
                frame = get_task.result()
                get_task = None  # reset for the next round
                try:
                    await self.process_frame(frame)
                    
                except asyncio.CancelledError:
                    print(f"[{self.name}] is cancelled")
                    
                except Exception as e:
                    print(f"[{self.name}] encountered an error: {e}")
                    
                finally:
                    self.input_queue.task_done()
                    
            # after processing the frame, check if we need to stop; if no frame was received, cancel the wait and exit
            if stop_task in done:
                if get_task is not None:
                    get_task.cancel()
                break