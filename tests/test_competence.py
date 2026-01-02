import sys
import os
import asyncio

# Ensure app module can be imported
sys.path.append(os.getcwd())

from app.schemas.intelligence import ClassifyRequest, ChatRequest
from app.services import classifier, chat

async def test_competence_control():
    print("=== [TEST] Phase 4: Competence & Control ===")
    
    # 1. Test Control (Kill Command)
    print("\n[1] Testing Kill Command (League of Legends)...")
    req_game = ClassifyRequest(
        active_window="League of Legends",
        windows=["League of Legends", "Discord"],
    )
    # We assume 'League of Legends' triggers high confidence PLAY in LLM
    # Note: LLM calls are non-deterministic, but our blacklist logic relies on exact string match in python if result is PLAY.
    
    resp_game = await classifier.classify_content(req_game)
    print(f"Result: {resp_game.result}")
    print(f"Command: {resp_game.command}")
    print(f"Message: {resp_game.message}")
    
    if resp_game.command == "KILL":
        print(">> PASS: Kill command issued.")
    else:
        print(">> FAIL: Kill command NOT issued (Check confidence or blacklist match).")

    # 2. Test Competence (Tech Support Persona)
    print("\n[2] Testing Competence (Tech Support)...")
    chat_req = ChatRequest(text="I keep getting NullPointerException in Java Spring Boot. How do I fix it?")
    chat_resp = await chat.chat_with_persona(chat_req)
    
    print(f"Chat Response: {chat_resp.text}")
    
    # Check for Sarcasm + Code
    is_sarcastic = any(x in chat_resp.text for x in ["하...", "몰라요", "거든요"])
    has_code = "```" in chat_resp.text or "if (" in chat_resp.text
    
    if has_code:
        print(">> PASS: Response contains technical solution.")
    else:
        print(">> FAIL: Response missing technical solution/code.")

if __name__ == "__main__":
    asyncio.run(test_competence_control())
