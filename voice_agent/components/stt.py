import asyncio
from abc import abstractmethod
from typing import AsyncGenerator

from voice_agent.components.base import PipelineComponent
from voice_agent.frame import AudioFrame, TextFrame

class BaseSTTComponent(PipelineComponent):
    """
    Base class for Speech-to-Text (STT) components.
    It manages two concurrent flows:
    1. Consuming incoming AudioFrames from the input queue and sending them to the STT service.
    2. Receiving transcription results from the STT service and pushing TextFrames downstream.
    """
    
    def __init__(self, name: str = "BaseSTT", queue_size: int = 100):
        super().__init__(name=name, queue_size=queue_size)
    
    @abstractmethod
    async def start_engine(self):
        """Initialize the connection or resources for the STT engine."""
        pass
        
    @abstractmethod
    async def send_audio(self, frame: AudioFrame):
        """Send a single audio frame to the STT engine/service."""
        pass

    @abstractmethod
    async def receive_transcriptions(self) -> AsyncGenerator[TextFrame, None]:
        """Yield TextFrames as transcriptions are received from the STT engine/service."""
        yield NotImplemented
        
    @abstractmethod
    async def stop_engine(self):
        """Clean up the connection or resources for the STT engine."""
        pass

    async def process_frame(self, frame):
        """
        Implementation of the PipelineComponent abstract method. 
        It filters for AudioFrames and sends them to the engine.
        """
        if isinstance(frame, AudioFrame):
            await self.send_audio(frame)
        else:
            # Pass through non-audio frames or ignore them
            pass

    async def _receive_loop(self):
        """
        A background task that continuously pulls transcriptions from the STT engine
        and pushes them to the next component in the pipeline.
        """
        try:
            async for text_frame in self.receive_transcriptions():
                if self._stop_event.is_set():
                    break
                await self.push(text_frame)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[{self.name}] Error in transcription receive loop: {e}")

    async def run(self):
        """
        Override the default run to spin up the STT engine and the receive loop 
        concurrently with the standard input queue processing loop.
        """
        await self.start_engine()
        
        # Start the background task to receive results from the STT engine
        receive_task = asyncio.create_task(self._receive_loop())
        
        try:
            # Let the standard PipelineComponent handle consuming the `self.input_queue`
            # and calling `self.process_frame()`
            await super().run()
        finally:
            # Clean up the task and engine when the component is stopped
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
                
            await self.stop_engine()
