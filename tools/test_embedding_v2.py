import os
import sys
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.memory import get_embeddings
from app.core.config import get_settings

def test_embeddings():
    print("=== Testing AWS Titan Embeddings v2 ===")
    
    settings = get_settings()
    print(f"Region: {settings.AWS_REGION}")
    
    try:
        embeddings = get_embeddings()
        print(f"Model ID: {embeddings.model_id}")
        
        text = "Hello, this is a test for Titan Embeddings v2."
        print(f"Embedding text: '{text}'")
        
        # Test query embedding
        vector = embeddings.embed_query(text)
        
        print(f"Success! Vector generated.")
        print(f"Vector Dimensions: {len(vector)}")
        print(f"First 5 dimensions: {vector[:5]}")
        
        # Titan v2 default dimension is 1024. v1 is 1536 (usually).
        if len(vector) == 1024:
            print("✅ Dimensions match Titan v2 default (1024).")
        else:
            print(f"⚠️ Dimensions: {len(vector)} (Check if this is expected)")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_embeddings()
