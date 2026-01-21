from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import httpx
from app.services.memory_service import memory_service
from app.core.config import get_settings
from langchain_core.documents import Document

router = APIRouter()
settings = get_settings()

class QuizWrongAnswer(BaseModel):
    question_id: int
    user_answer: str
    correct_answer: str
    question_text: Optional[str] = None

class QuizResultRequest(BaseModel):
    topic: str
    score: int
    max_score: int
    wrong_answers: List[QuizWrongAnswer] = []
    user_id: str = "user" # Default user

class QuizGenerateRequest(BaseModel):
    topic: str
    difficulty: str = "Medium"

from app.services import planner

@router.post("/generate")
async def generate_quiz(request: QuizGenerateRequest):
    """
    Generates a technical quiz based on topic and difficulty.
    Replaces gRPC implementation to avoid ALB/Protocol issues.
    """
    print(f"🧠 [Quiz] REST Generation Request: {request.topic} ({request.difficulty})")
    try:
        quizzes = await planner.generate_quiz(request.topic, request.difficulty)
        return {"status": "success", "quizzes": quizzes}
    except Exception as e:
        print(f"❌ [Quiz] Generation Failed: {e}")
        return {"status": "error", "message": str(e), "quizzes": []}

async def forward_log_to_data_server(payload: dict):
    """
    Background Task: Forward generic log to jiaa-server-data (InfluxDB)
    """
    data_server_url = "http://jiaa-server-data.jiaa.svc.cluster.local:8082" 
    # Fallback for local dev if needed, logic to determine env could be here
    # Since user emphasized ALB/K8s, we use strict internal DNS or external logic.
    # But usually internal DNS is safer.
    
    # However, if testing locally (outside k8s), this DNS won't resolve.
    # Using a simple check or just env var for data server URL would be better.
    # We will assume K8s env for now as per instructions "Deploying...".
    
    # Actually, for local dev (Windows), we might need localhost or docker service name.
    # Let's use an env var if available, else K8s DNS.
    url = f"{settings.DATA_SERVER_URL}/api/v1/log" if hasattr(settings, "DATA_SERVER_URL") else "http://jiaa-server-data.jiaa.svc.cluster.local:8082/api/v1/log"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=5.0)
            if response.status_code != 200:
                print(f"❌ [Quiz] Forwarding Log Failed: {response.text}")
            else:
                print(f"✅ [Quiz] Log Forwarded to Data Server")
    except Exception as e:
        print(f"❌ [Quiz] Forwarding Error: {e}")

@router.post("/result")
async def save_quiz_result(request: QuizResultRequest, background_tasks: BackgroundTasks):
    """
    Receives Quiz Result from Client.
    1. Saves context (wrong_answers) to PGVector (AI Memory).
    2. Forwards Log to Data Server (InfluxDB).
    """
    print(f"📝 [Quiz] Received Result: {request.topic} ({request.score}/{request.max_score})")

    # 1. Save Qualitative Context to AI Memory (PGVector)
    # We only save "What I got wrong" so the AI knows what to coach about.
    if request.wrong_answers:
        context_text = f"Quiz: {request.topic}. Score: {request.score}. I got these wrong: "
        for wa in request.wrong_answers:
             context_text += f"\n- Q: {wa.question_text or '?'}, My Answer: {wa.user_answer} (Correct: {wa.correct_answer})"
        
        # Save to STM/LTM via memory service
        # We treat this as a "STUDY" event
        memory_service._save_event(context_text, "QUIZ_RESULT", metadata={"score": request.score, "topic": request.topic})
        print("✅ [Memory] Saved Quiz Context to AI Memory.")

    # 2. Forward to Data Server (Data Trinity)
    # This ensures InfluxDB gets the hard data
    log_payload = {
        "user_id": request.user_id,
        "category": "STUDY",
        "type": "QUIZ",
        "timestamp": None, # Use server time
        "data": {
            "score": request.score,
            "max": request.max_score,
            "action_detail": request.topic,
            "wrong_count": len(request.wrong_answers),
            "wrong_answers": [wa.dict() for wa in request.wrong_answers]
        }
    }
    
    background_tasks.add_task(forward_log_to_data_server, log_payload)

    return {"status": "ok", "message": "Quiz result processed"}
