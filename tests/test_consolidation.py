import sys
import os
import asyncio
# Ensure app module can be imported
sys.path.append(os.getcwd())

from app.services.memory_service import memory_service

async def test_consolidation():
    print("=== [TEST] Memory Consolidation Flow ===")
    
    # 1. Populate STM
    print("\n1. Generating dummy traffic (STM)...")
    memory_service.save_violation("YouTube: Funny Cat Video")
    memory_service.save_achievement("GitHub: Spring Boot Source Code")
    memory_service.save_violation("Netflix: Squid Game 2")
    
    # 2. Check Context (Should have STM)
    print("\n2. Checking Context (Before Consolidation)...")
    context = memory_service.get_user_context("나 뭐했어?")
    print(context)
    
    # 3. Trigger Consolidation
    print("\n3. Triggering Consolidation (Sleep Routine)...")
    print("(Expect LTM errors if DB is not reachable, but code shouldn't crash)")
    await memory_service.consolidate_memory()
    
    # 4. Done
    print("\n4. Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_consolidation())
