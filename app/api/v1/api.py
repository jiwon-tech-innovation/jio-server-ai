from fastapi import APIRouter
from app.api.v1.endpoints import intelligence, prediction, review

api_router = APIRouter()
api_router.include_router(intelligence.router, tags=["intelligence"])
api_router.include_router(prediction.router, tags=["prediction"])
api_router.include_router(review.router, tags=["review"])
