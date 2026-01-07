import sys
import os
from langchain_core.documents import Document

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.memory import get_vector_store

def init_stm():
    print("🚀 Initializing STM (Redis)...")
    try:
        stm = get_vector_store()
        # Adding a single dummy document forces index creation
        dummy_doc = Document(page_content="System initialization entry.", metadata={"type": "SYSTEM_INIT", "timestamp": "2024-01-01T00:00:00"})
        ids = stm.add_documents([dummy_doc])
        print(f"✅ STM Index Created. ID: {ids}")
    except Exception as e:
        print(f"❌ STM Init Error: {e}")

if __name__ == "__main__":
    init_stm()
