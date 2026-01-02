import sys
import os
import asyncio
from datetime import datetime

# Ensure app module can be imported
sys.path.append(os.getcwd())

from app.services.memory_service import memory_service

def test_memory_direct():
    print("=== [TEST] Memory Service Direct Test ===")
    
    # 1. Save Violation
    print("1. Saving Violation (YouTube)...")
    memory_service.save_violation("YouTube: Funny Cat Video", source="URL")
    
    # 2. Save Achievement
    print("2. Saving Achievement (Spring Boot)...")
    memory_service.save_achievement("GitHub: Spring Boot Source Code")
    
    # 3. Retrieve Context
    print("3. Retrieving Context (Query: '나 뭐했어?')...")
    context = memory_service.get_user_context("나 뭐했어?")
    
    print("\n--- RETRIEVED CONTEXT ---")
    print(context)
    print("-------------------------\n")
    
    if "Funny Cat Video" in context and "Spring Boot" in context:
        print(">> PASS: Context retrieval successful.")
    else:
        print(">> FAIL: Context missing items.")

if __name__ == "__main__":
    test_memory_direct()
