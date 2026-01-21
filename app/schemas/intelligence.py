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
    content_type: str = "WINDOW" # URL or WINDOW
    content: Optional[str] = None # URL string or other content
    
    process_info: Optional[ProcessInfo] = None
    windows: Optional[List[str]] = [] # Background windows list
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

# Quiz
class QuizResultRequest(BaseModel):
    topic: str
    score: int
    max_score: int

class QuizGenerateRequest(BaseModel):
    topic: str
    difficulty: str

# STT
class STTResponse(BaseModel):
    text: str

# Chat
class ChatRequest(BaseModel):
    text: str
    user_id: Optional[str] = "dev1"

class ChatResponse(BaseModel):
    intent: str # COMMAND, CHAT
    judgment: str # STUDY, PLAY, NEUTRAL
    action_code: str # OPEN_APP, NONE, BLOCK_APP, MINIMIZE_APP, KILL_APP
    action_detail: Optional[str] = "" # "VSCode"
    message: str # "오, 드디어..."
    emotion: Optional[str] = "NORMAL" # "NORMAL", "ANGRY", "LOVE", "SILLY", "STUNNED", "CRY", "LAUGH", "PUZZLE"

    # [Multi-Command Support]
    multi_actions: Optional[List[Dict[str, Any]]] = None

# Subgoals (New)
class SubgoalGenerateRequest(BaseModel):
    goal_text: str

class SubgoalResponse(BaseModel):
    status: str
    subgoals: List[str]
