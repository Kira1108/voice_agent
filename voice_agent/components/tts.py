import asyncio
import re
from abc import abstractmethod
from typing import AsyncGenerator

from voice_agent.components.base import PipelineComponent
from voice_agent.frame.base import Frame, AudioFrame, TextStreamFrame
from voice_agent.utils.sentence_splitter import SENTENCE_ENDING_PUNCTUATION_STR

class BaseTTSComponent(PipelineComponent):
    """
    Base class for Text-to-Speech (TTS) components.
    It manages two concurrent flows:
    1. Consuming incoming TextStreamFrames, buffering chunks until a sentence is complete 
       (or length limit is reached) and putting them into a synthesis queue.
    2. A background loop pulling complete sentences from the synthesis queue, calling the 
       TTS engine to synthesize, and pushing AudioFrames downstream.
    """
    
    def __init__(self, name: str = "BaseTTS", queue_size: int = 100, flush_length: int = 50):
        super().__init__(name=name, queue_size=queue_size)
        
        # Queue for holding fully formed sentences ready for audio generation
        self.sentence_queue = asyncio.Queue()
        
        # Buffer to accumulate streaming text chunks
        self._buffer = ""
        self.flush_length = flush_length
        self._punctuation_pattern = re.compile(f"([{SENTENCE_ENDING_PUNCTUATION_STR}]+)")

    @abstractmethod
    async def start_engine(self):
        """Initialize the connection or load the model for the TTS engine."""
        pass

    @abstractmethod
    async def synthesize(self, text: str) -> AsyncGenerator[AudioFrame, None]:
        """Yield AudioFrames as speech audio generated from the given text."""
        raise NotImplementedError
        yield
        
    @abstractmethod
    async def stop_engine(self):
        """Clean up the connection or resources for the TTS engine."""
        pass

    async def process_frame(self, frame: Frame):
        """
        Filters for TextStreamFrames, buffering text and parsing it into discrete 
        sentences based on punctuation or length limits.
        """
        if isinstance(frame, TextStreamFrame):
            self._buffer += frame.text_chunk
            
            # If this is the end of the AI's response block, flush everything remaining
            if frame.is_end:
                sentence = self._buffer.strip()
                if sentence:
                    await self.sentence_queue.put(sentence)
                self._buffer = ""
                return
            
            # Otherwise, keep splitting by punctuation or length limit
            while True:
                # Find punctuation
                match = self._punctuation_pattern.search(self._buffer)
                
                if match:
                    # Flush up to and including the punctuation
                    split_idx = match.end()
                    sentence = self._buffer[:split_idx].strip()
                    if sentence:
                        await self.sentence_queue.put(sentence)
                    self._buffer = self._buffer[split_idx:]
                    
                elif len(self._buffer) >= self.flush_length:
                    # Flush by length limit if no punctuation is found for a long time
                    sentence = self._buffer.strip()
                    if sentence:
                        await self.sentence_queue.put(sentence)
                    self._buffer = ""
                    
                else:
                    # Not enough text to flush, wait for more chunks
                    break

    async def _synthesize_loop(self):
        """
        Background task that continuously pulls buffered sentences and runs the TTS generator.
        """
        try:
            while not self._stop_event.is_set():
                get_task = asyncio.create_task(self.sentence_queue.get())
                stop_task = asyncio.create_task(self._stop_event.wait())
                
                done, pending = await asyncio.wait(
                    [get_task, stop_task], 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if get_task in done:
                    sentence = get_task.result()
                    
                    # Perform actual text-to-speech generation
                    try:
                        async for audio_frame in self.synthesize(sentence):
                            if self._stop_event.is_set():
                                break
                            await self.push(audio_frame)
                    except Exception as e:
                        print(f"[{self.name}] Error synthesizing sentence '{sentence}': {e}")
                    finally:
                        self.sentence_queue.task_done()
                        
                if stop_task in done:
                    if get_task is not None and not get_task.done():
                        get_task.cancel()
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[{self.name}] Error in synthesis loop: {e}")

    async def run(self):
        """
        Override run to spin up the TTS engine and synthesis loop, concurrently 
        with the standard queue processing loop for text aggregation.
        """
        await self.start_engine()
        
        # Start the background task to pop complete sentences and generate audio
        synthesize_task = asyncio.create_task(self._synthesize_loop())
        
        try:
            # Consume the raw input_queue for incoming TextStreamFrames (Base Pipeline component loop)
            await super().run()
        finally:
            synthesize_task.cancel()
            try:
                await synthesize_task
            except asyncio.CancelledError:
                pass
                
            await self.stop_engine()