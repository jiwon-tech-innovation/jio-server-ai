from fastapi import APIRouter, BackgroundTasks
from app.services.memory_service import memory_service

router = APIRouter()

@router.post("/consolidate")
async def consolidate_memory(background_tasks: BackgroundTasks):
    """
    Triggers memory consolidation manually.
    Called by Desktop Client on shutdown.
    
    1. Summarizes Short-Term Memory (Redis).
    2. Saves summary to Long-Term Memory (Postgres LTM).
    3. Clears Short-Term Memory.
    """
    # Use background task to avoid blocking the response if it takes time
    background_tasks.add_task(memory_service.consolidate_memory)
    
    return {"status": "ACCEPTED", "message": "Memory consolidation started in background."}
