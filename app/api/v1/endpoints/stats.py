from fastapi import APIRouter, Depends
from typing import Any
from app.services.statistic_service import statistic_service

router = APIRouter()

@router.get("/all")
async def get_dashboard_stats(user_id: str = "dev1") -> Any:
    """
    Get all statistics for the dashboard.
    Currently returns 'weeklyStats' for the chart.
    Default user_id is 'dev1' for demo purposes.
    """
    print(f"📊 [Stats] Fetching dashboard stats for {user_id}")
    try:
        weekly_stats = await statistic_service.get_weekly_stats(user_id)
        return {
            "success": True,
            "data": {
                "weeklyStats": weekly_stats
            }
        }
    except Exception as e:
        print(f"❌ [Stats] Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {
                "weeklyStats": []
            }
        }
