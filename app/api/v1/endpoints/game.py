from fastapi import APIRouter
from app.schemas.game import GameDetectRequest, GameDetectResponse
from app.services import game_detector

router = APIRouter()

@router.post("/detect-game", response_model=GameDetectResponse)
async def detect_game(request: GameDetectRequest):
    """
    Analyzes the list of running apps to detect games.
    """
    return await game_detector.detect_games(request)
