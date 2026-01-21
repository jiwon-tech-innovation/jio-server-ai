#!/usr/bin/env python3
"""
Quick script to set trust score for wonji052271@gmail.com
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.memory_service import memory_service

# Target User
USER_ID = "wonji052271@gmail.com"
TARGET_TRUST_SCORE = 90  # High trust score

def set_trust_score():
    print(f"🚀 Setting Trust Score for {USER_ID}...")
    
    try:
        # Get current trust score
        current_score = memory_service.get_trust_score(USER_ID)
        print(f"   - Current Trust Score: {current_score}")
        
        # Set new trust score directly in Redis
        key = f"user:{USER_ID}:trust_score"
        client = memory_service._get_redis_client()
        client.set(key, TARGET_TRUST_SCORE)
        client.close()
        
        # Verify
        new_score = memory_service.get_trust_score(USER_ID)
        print(f"   - New Trust Score: {new_score}")
        print(f"✅ Trust Score Updated: {current_score} → {new_score}")
        
    except Exception as e:
        print(f"❌ Failed to update trust score: {e}")
        raise

if __name__ == "__main__":
    set_trust_score()
