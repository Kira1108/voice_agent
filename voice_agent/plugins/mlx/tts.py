import asyncio
from typing import AsyncGenerator
import numpy as np

from mlx_audio.tts.utils import load_model

from voice_agent.components.tts import BaseTTSComponent
from voice_agent.frame.base import AudioFrame
from pathlib import Path

DEFAULT_VOICE_REF = Path(__file__).parent.parent.parent / "voices" / "bejing-woman.wav"

_GLOBAL_MLX_MODEL = None

class MlxTTSComponent(BaseTTSComponent):
    """
    MLX implementation of the TTS component.
    Wraps the synchronous Qwen3-TTS generation softly enough to yield control back to asyncio.
    """
    
    def __init__(self, 
                 model_id: str = "/Users/wanghuan/.cache/huggingface/hub/models--mlx-community--Qwen3-TTS-12Hz-1.7B-Base-8bit/snapshots/e7dd0585652209fa0d7783659aad4e8a324de11c", 
                 voice: str = "Dylan",
                 streaming_interval: float = 0.32,
                 name: str = "MlxTTS", 
                 queue_size: int = 100):
        super().__init__(name=name, queue_size=queue_size)
        self.model_id = model_id
        self.voice = voice
        self.streaming_interval = streaming_interval
        self.model = None

    async def start_engine(self):
        """Loads the MXL TTS model and performs a dummy run to warm up the GPU compilation."""
        global _GLOBAL_MLX_MODEL
        
        if _GLOBAL_MLX_MODEL is None:
            print(f"[{self.name}] Global MLX model not found. Loading {self.model_id}...")
            _GLOBAL_MLX_MODEL = load_model(self.model_id)
            
            print(f"[{self.name}] Warming up the MLX GPU Graph (Metal JIT compilation)...")
            warmup_gen = _GLOBAL_MLX_MODEL.generate("a", voice=self.voice, stream=True, streaming_interval=self.streaming_interval)
            for _ in warmup_gen:
                await asyncio.sleep(0.001)
                
            print(f"[{self.name}] ✨ MLX model loaded and Metal Graph compiled globally. Warmup complete.")
        else:
            print(f"[{self.name}] Using cached global MLX model.")
            
        self.model = _GLOBAL_MLX_MODEL

    async def synthesize(self, text: str) -> AsyncGenerator[AudioFrame, None]:
        """
        Takes a full sentence and yields AudioFrames chunk by chunk.
        """
        if not text or not self.model:
            return

        print(f"[{self.name}] Synthesizing: {text}")
        
        ref_audio_path_str = str(DEFAULT_VOICE_REF)
        
        # Initialize the synchronous mlx_audio generator
        sync_gen = self.model.generate(
            text=text,
            voice=self.voice,
            stream=True,
            streaming_interval=self.streaming_interval,
            seed = 1.0,
            ref_audio=ref_audio_path_str
        )
        
        while not self._stop_event.is_set():
            try:
                result = next(sync_gen)
                audio_np = result.audio
                
                if hasattr(audio_np, "tolist") and not isinstance(audio_np, np.ndarray):
                    audio_np = np.array(audio_np.tolist(), dtype=np.float32)

                if audio_np.dtype == np.float32 or audio_np.dtype == np.float64:
                    audio_np = np.clip(audio_np, -1.0, 1.0)
                    audio_int16 = (audio_np * 32767.0).astype(np.int16)
                    audio_bytes = audio_int16.tobytes()
                else:
                    audio_bytes = audio_np.tobytes()

                yield AudioFrame(audio_data=audio_bytes)
                
                await asyncio.sleep(0)
                
            except StopIteration:
                break
            except Exception as e:
                print(f"[{self.name}] MLX generation error: {e}")
                break

    async def stop_engine(self):
        """Cleanup, if any."""
        self.model = None
        