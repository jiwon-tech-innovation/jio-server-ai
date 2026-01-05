from fastapi import APIRouter
<<<<<<< HEAD
from app.api.v1.endpoints import intelligence, prediction, review, memory, game

api_router = APIRouter()
api_router.include_router(intelligence.router, tags=["intelligence"])
api_router.include_router(prediction.router, tags=["prediction"])
api_router.include_router(review.router, tags=["review"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(game.router, tags=["game"])
