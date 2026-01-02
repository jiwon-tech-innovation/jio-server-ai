import asyncio
import sys
import os
import json

# Add root folder to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.intelligence import ChatRequest
from app.services import chat

async def run_test(scenario_name, input_voice_text):
    """
    Simulates the pipeline:
    Voice Input (Mock STT) -> AI Logic -> JSON Output
    """
    print(f"\n{'='*50}")
    print(f"🎬 Scenario: {scenario_name}")
    print(f"🎤 [Voice Input] (Simulated STT): \"{input_voice_text}\"")
    
    # 1. AI Logic (The Core Brain)
    # This is exactly what grpc_server.py calls after STT
    try:
        response = await chat.chat_with_persona(ChatRequest(text=input_voice_text))
        
        print("\n🤖 [AI Judgment Result]")
        print(f"  - Intent:       {response.intent}")
        print(f"  - Judgment:     {response.judgment} {'(✅ Allowed)' if response.judgment == 'STUDY' else '(❌ Blocked/Neutral)'}")
        print(f"  - Action Code:  {response.action_code}")
        print(f"  - Action Detail:{response.action_detail}")
        print(f"  - Message:      \"{response.message}\"")
        
        # 2. JSON check (Dev 4 Compatibility)
        intent_data = {
            "intent": response.intent,
            "judgment": response.judgment,
            "action_code": response.action_code,
            "action_detail": response.action_detail,
            "message": response.message
        }
        print(f"\n📦 [JSON Output for Dev 4]:")
        print(json.dumps(intent_data, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Error: {e}")

async def main():
    print("🚀 Starting Logic Verification (Audio -> AI Brain Test)...")
    
    # Scene 1: Study Command
    await run_test("A: Study Start", "VSCode 켜줘")
    
    # Scene 2: Distraction Command
    await run_test("B: Distraction Attempt", "유튜브 켜줘")
    
    # Scene 3: Chat/Complaint
    await run_test("C: Complaint/Chat", "아 진짜 너무 어렵다... 하기 싫어")

if __name__ == "__main__":
    asyncio.run(main())
