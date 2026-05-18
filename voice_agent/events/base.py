from dataclasses import dataclass
from typing import Any
from enum import Enum, auto

class EventType(Enum):
    USER_STARTED_SPEAKING = auto()
    USER_STOPPED_SPEAKING = auto()
    AGENT_STARTED_SPEAKING = auto()
    AGENT_STOPPED_SPEAKING = auto()
    CANCEL_PIPELINE = auto()
    SESSION_ENDED = auto()
    
@dataclass
class VoiceAgentEvent:
    type: EventType
    data: Any = None