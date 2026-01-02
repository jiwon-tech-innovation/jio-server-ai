
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.classifier import classify_content
from app.services.chat import chat_with_persona
from app.schemas.intelligence import ClassifyRequest, ProcessInfo, ChatRequest, SystemMetrics, MediaInfo

async def test_classification_state():
    print("\n[1] Testing Classification State...")
    
    # CASE 1: STUDY (Coding)
    req_study = ClassifyRequest(
        process_info=ProcessInfo(process_name="Code.exe", window_title="main.py - JIAA"),
        windows=["Code.exe", "Chrome.exe"]
    )
    res_study = await classify_content(req_study)
    print(f"CASE 1 (Coding): Result={res_study.result}, State={res_study.state}")
    assert res_study.state == "STUDY", f"Expected STUDY, got {res_study.state}"

    # CASE 2: PLAY (Game)
    req_play = ClassifyRequest(
        process_info=ProcessInfo(process_name="League of Legends.exe", window_title="League of Legends (TM) Client"),
        windows=["League of Legends.exe"]
    )
    res_play = await classify_content(req_play)
    print(f"CASE 2 (Game): Result={res_play.result}, State={res_play.state}")
    assert res_play.state == "PLAY", f"Expected PLAY, got {res_play.state}"
    
    print(">> PASS: Classification State is correct.")

async def test_chat_state():
    print("\n[2] Testing Chat State...")
    
    # CASE 1: Study Question
    req_tech = ChatRequest(text="JPA에서 N+1 문제가 뭐야?")
    res_tech = await chat_with_persona(req_tech)
    print(f"CASE 1 (Tech): Type={res_tech.type}, State={res_tech.state}")
    assert res_tech.state == "CHAT", f"Expected CHAT, got {res_tech.state}"
    
    # CASE 2: Chat
    req_chat = ChatRequest(text="나 오늘 너무 피곤해...")
    res_chat = await chat_with_persona(req_chat)
    print(f"CASE 2 (Chat): Type={res_chat.type}, State={res_chat.state}")
    assert res_chat.state == "CHAT", f"Expected CHAT, got {res_chat.state}"

    print(">> PASS: Chat State is correct.")

async def main():
    print("=== [TEST] Phase 5: State-Awareness ===")
    try:
        await test_classification_state()
        await test_chat_state()
        print("\nALL TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
