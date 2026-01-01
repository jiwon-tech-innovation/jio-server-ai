from pydantic import BaseModel
from typing import Optional

# Classification
class ClassifyRequest(BaseModel):
    content_type: str  # URL, PROCESS_NAME, or BEHAVIOR (e.g., "SLEEPING", "AWAY")
    content: str       # The actual data (e.g., "League of Legends", "USER_IDLE_30MIN")

class ClassifyResponse(BaseModel):
    result: str # STUDY, PLAY
    reason: str
    confidence: float = 1.0

# Solution (Error Solver)
class SolveRequest(BaseModel):
    log: str           # Spec says "log"
    audio_decibel: int # Spec says "audio_decibel" (e.g., 95)

class SolveResponse(BaseModel):
    solution_code: str    # Spec says "solution_code"
    comfort_message: str  # Spec says "comfort_message"
    til_content: str      # Spec says "til_content" (Today I Learned)

# STT
class STTResponse(BaseModel):
    text: str

# Chat
class ChatRequest(BaseModel):
    text: str

class ChatResponse(BaseModel):
    type: str = "CHAT"
    text: str
    command: Optional[str] = None
    parameter: Optional[str] = None

