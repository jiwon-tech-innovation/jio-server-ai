import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.append(".")

# Mock Settings to prevent real DB connection attempts during import
from app.core.config import Settings
mock_settings = Settings()
mock_settings.BEDROCK_REGION = "us-east-1"
mock_settings.AWS_REGION = "us-east-1"

async def test_hybrid_memory():
    print("=== Testing Hybrid Memory System (Integration) ===")
    
    # Ensure module is loaded for patch to work
    import app.services.chat 

    # 1. Mock Dependencies
    with patch("app.services.chat.memory_service") as mock_memory, \
         patch("app.services.chat.statistic_service") as mock_stats, \
         patch("app.services.chat.get_llm") as mock_get_llm:
         
        # Mock Semantic Memory (Vector)
        mock_memory.get_user_context.return_value = "- [Semantic] User said they would study hard."
        
        # Mock Statistical Memory (InfluxDB)
        # Ensure it is AsyncMock because the code awaits it
        mock_stats.get_recent_summary = AsyncMock()
        mock_stats.get_recent_summary.return_value = {
            "study_count": 30,  # minutes
            "play_count": 120,  # minutes
            "ratio": 80.0, 
            "violations": ["Played LoL (2026-01-05 14:00)", "YouTube (2026-01-04 10:00)"]
        }
        
        # Mock LLM Chain
        mock_llm_instance = MagicMock()
        mock_chain = AsyncMock()
        # Mock Response content
        mock_chain.ainvoke.return_value = MagicMock(content="""
        {
            "intent": "COMMAND",
            "judgment": "PLAY",
            "action_code": "NONE",
            "message": "지금 통계표 안 보여요? 8번이나 놀아놓고 또? 양심 가출?"
        }
        """)
        mock_llm_instance.__or__.return_value = mock_chain
        mock_get_llm.return_value = mock_llm_instance
        
        # 2. Call Chat Service
        from app.services.chat import chat_with_persona
        from app.schemas.intelligence import ChatRequest
        
        request = ChatRequest(text="게임 한 판만 더 할게")
        response = await chat_with_persona(request)
        
        # 3. Verify Interactions
        print(f"Input: {request.text}")
        print(f"Response Message: {response.message}")
        
        # Verify Semantic Call
        mock_memory.get_user_context.assert_called_with(request.text)
        print("[✔] Semantic Memory retrieved.")
        
        # Verify Statistical Call
        mock_stats.get_recent_summary.assert_called()
        print("[✔] Statistical Summary retrieved.")
        
        # Verify Prompt Content
        call_args = mock_chain.ainvoke.call_args
        if call_args:
            prompt_sent = call_args[0][0]
            print("\n--- Prompt Snippet ---")
            # Check for injection
            if "Judgment: BAD" in prompt_sent:
                print("[✔] 'BAD' Judgment Guide injected.")
            else:
                 print("[X] Judgment Guide MISSING.")
                 
            if "Recent Violations:" in prompt_sent:
                print("[✔] Violation List injected.")
            
            if "Play Ratio: 80.0%" in prompt_sent:
                print("[✔] Play Ratio injected.")
                
            # print(prompt_sent) # Uncomment to debug full prompt

if __name__ == "__main__":
    asyncio.run(test_hybrid_memory())
