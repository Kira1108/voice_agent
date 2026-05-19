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
    
    
@dataclass
class TextStreamFrame(Frame):
    text_chunk:str
    response_id:str
    is_first:bool
    is_end:bool