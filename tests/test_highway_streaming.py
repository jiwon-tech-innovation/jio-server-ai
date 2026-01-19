"""
Highway AI Streaming Test Script
Tests the chat_with_persona_stream() function locally.
"""
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.intelligence import ChatRequest
from app.services.chat import chat_with_persona_stream

async def test_streaming():
    print("=" * 60)
    print("🚀 Highway AI Streaming Test")
    print("=" * 60)
    
    # Test request
    request = ChatRequest(
        text="안녕하세요! 오늘 공부 시작할게요.",
        user_id="test_user"
    )
    
    print(f"\n📝 Test Input: {request.text}")
    print("\n--- Streaming Output ---\n")
    
    chunk_count = 0
    full_text = ""
    
    async for text_chunk, is_complete, metadata in chat_with_persona_stream(request):
        if is_complete:
            print(f"\n--- Stream Complete ---")
            print(f"📊 Total Chunks: {chunk_count}")
            print(f"📝 Full Text: {full_text}")
            print(f"🎯 Intent Data: {metadata}")
        else:
            chunk_count += 1
            full_text += text_chunk
            print(f"[Chunk {chunk_count}] {text_chunk}", flush=True)
    
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_streaming())
