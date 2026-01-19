"""
Highway AI - Pure LLM Streaming Test
Tests llm.astream() directly without Redis/Memory dependencies.
"""
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.llm import get_llm, HAIKU_MODEL_ID

async def test_llm_streaming():
    print("=" * 60)
    print("🚀 Pure LLM Streaming Test (No Redis)")
    print("=" * 60)
    
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.1)
    
    prompt = """You are Alpine, an AI assistant.
Respond in Korean, naturally.
Output format: First say something, then output [INTENT] on a new line, then output JSON.

Example:
네, 알겠습니다 주인님!
[INTENT]
{"intent": "CHAT", "emotion": "NORMAL"}

User says: 안녕하세요!

Respond:"""
    
    print(f"\n📝 Prompt sent to LLM")
    print("\n--- Streaming Output ---\n")
    
    chunk_count = 0
    full_response = ""
    
    try:
        async for chunk in llm.astream(prompt):
            chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
            chunk_count += 1
            full_response += chunk_text
            
            # Print each chunk as it arrives
            print(f"[{chunk_count}] {repr(chunk_text)}", flush=True)
        
        print("\n--- Stream Complete ---")
        print(f"📊 Total Chunks: {chunk_count}")
        print(f"\n📝 Full Response:\n{full_response}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_llm_streaming())
