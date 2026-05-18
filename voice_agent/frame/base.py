from abc import ABC
from dataclasses import dataclass

@dataclass
class Frame(ABC): 
    pass

@dataclass
class AudioFrame(Frame):
    audio_data: bytes
    
@dataclass
class TextFrame(Frame):
    text: str