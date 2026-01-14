from fastapi import APIRouter, UploadFile, File
from app.schemas.intelligence import ClassifyRequest, ClassifyResponse, SolveRequest, SolveResponse, STTResponse, ChatRequest, ChatResponse
from app.services import classifier, solver, stt, chat
from app.services.memory_service import memory_service

router = APIRouter()

@router.post("/classify", response_model=ClassifyResponse)
async def classify_content(request: ClassifyRequest):
    """
    Classifies content (URL, Window Title, Behavior) using Claude 3.5 Haiku.
    """
    return await classifier.classify_content(request)

@router.post("/solve", response_model=SolveResponse)
async def solve_error(request: SolveRequest):
    """
    Analyzes error logs & audio decibels using Claude 3.5 Sonnet.
    Returns: Solution Code, Comfort Message, TIL.
    """
    return await solver.solve_error(request)

@router.post("/stt", response_model=STTResponse)
async def speech_to_text(file: UploadFile = File(...)):
    """
    Transcribes audio file using OpenAI Whisper.
    """
    return await stt.transcribe_audio(file)

@router.post("/chat", response_model=ChatResponse)
async def intelligent_chat(request: ChatRequest):
    """
    Tsundere Chatbot API.
    Input: {"text": "question"}
    Output: {"type": "CHAT", "text": "Answer with attitude"}
    """
    return await chat.chat_with_persona(request)

@router.post("/chat/audio", response_model=ChatResponse)
async def voice_chat(file: UploadFile = File(...)):
    """
    Voice Interaction API.
    Audio -> STT -> Chat -> Text Response.
    """
    # 1. STT
    stt_result = await stt.transcribe_audio(file)
    user_text = stt_result.text
    
    # 2. Chat with Persona
    # Note: We can include the interpreted text in the response if needed, 
    # but for now we adhere to ChatResponse format.
    chat_request = ChatRequest(text=user_text)
    response = await chat.chat_with_persona(chat_request)
    
    # response.text = f"(You said: {user_text})\n{response.text}"
    
    return response


@router.post("/memory/consolidate")
async def manual_memory_consolidation():
    """
    [Admin/System] Trigger Daily Memory Consolidation.
    Moves STM (Redis) -> LTM (PGVector) and resets Short-Term Memory.
    """
    print("📢 [API] Manual Memory Consolidation Triggered")
    await memory_service.consolidate_memory()
    return {"status": "success", "message": "Memory consolidation started (Check server logs)"}


