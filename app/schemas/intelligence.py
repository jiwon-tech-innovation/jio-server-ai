from pydantic import BaseModel
from typing import Optional

# Classification
from typing import List, Dict, Any

class ProcessInfo(BaseModel):
    process_name: str # e.g. "chrome.exe"
    window_title: str # e.g. "Spring Boot Tutorial - YouTube"

class MediaInfo(BaseModel):
    app: Optional[str] = None
    artist: Optional[str] = None
    track: Optional[str] = None
    title: Optional[str] = None

class SystemMetrics(BaseModel):
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    volume_level: int = 50 # 0-100
    uptime_seconds: float = 0.0 # Session duration

class ClassifyRequest(BaseModel):
    # Simplified Input (No KPM, No Mouse)
    process_info: ProcessInfo 
    windows: List[str] # Background windows list
    media_info: Optional[MediaInfo] = None
    system_metrics: Optional[SystemMetrics] = None

class ClassifyResponse(BaseModel):
    result: str # STUDY, PLAY
    state: str # STUDY, PLAY (Strict State for Client)
    reason: str
    confidence: float = 1.0
    message: Optional[str] = None 
    command: Optional[str] = None 

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
    state: str # CHAT (includes Study Qs), SYSTEM
    text: str
    command: Optional[str] = None
    parameter: Optional[str] = None

