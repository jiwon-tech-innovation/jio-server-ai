from pydantic import BaseModel, Field
from typing import List, Optional

class GameDetectRequest(BaseModel):
    apps: List[str] = Field(..., description="List of running application names")

class GameDetectResponse(BaseModel):
    is_game_detected: bool = Field(..., description="Whether a game is detected")
    target_app: Optional[str] = Field(None, description="The name of the detected game app")
    detected_games: List[str] = Field(default_factory=list, description="List of all detected games")
    message: str = Field(..., description="Reasoning or message")
    confidence: float = Field(0.0, description="Confidence score")
