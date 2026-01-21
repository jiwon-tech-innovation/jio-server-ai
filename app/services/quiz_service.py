"""
Quiz Service - Fetches quiz results from jiaa-auth database
"""
import httpx
import os
from datetime import datetime

class QuizService:
    def __init__(self):
        # jiaa-auth API URL (K8s internal or ALB)
        self.base_url = os.environ.get("AUTH_API_URL", "http://jiaa-auth:8080")
    
    async def get_daily_quiz_results(self, user_id: str, date_str: str = None, token: str = None) -> list[str]:
        """
        Fetches quiz results for a specific date from jiaa-auth DB.
        Returns formatted strings for TIL report.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        url = f"{self.base_url}/api/quiz/daily?date={date_str}"
        
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("data"):
                        results = []
                        for quiz in data["data"]:
                            # Format: "Topic: Score/MaxScore (Percentage%)"
                            topic = quiz.get("topic", "Unknown")
                            score = quiz.get("score", 0)
                            max_score = quiz.get("maxScore", 0)
                            pct = quiz.get("percentage", 0)
                            results.append(f"- {topic}: {score}/{max_score} ({pct:.1f}%)")
                        return results
                    return []
                else:
                    print(f"[QuizService] API Error: {response.status_code}")
                    return []
        except Exception as e:
            print(f"[QuizService] Request Error: {e}")
            return []

quiz_service = QuizService()
