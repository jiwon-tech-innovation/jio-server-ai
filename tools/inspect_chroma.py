import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_community.vectorstores import Chroma
from app.core.memory import get_embeddings

def inspect_chroma(dir_name):
    print(f"--- Inspecting: {dir_name} ---")
    if not os.path.exists(dir_name):
        print(f"Directory {dir_name} does not exist.")
        return

    try:
        db = Chroma(
            persist_directory=dir_name, 
            embedding_function=get_embeddings()
        )
        # Chroma's API might vary slightly by version, but get() usually returns all metadata/ids
        count = db._collection.count()
        print(f"Document Count: {count}")
        
        if count > 0:
            print("Sample Documents (Top 2):")
            # peek returns a dict with 'ids', 'embeddings', 'documents', 'metadatas'
            data = db._collection.peek(limit=2)
            for i, doc in enumerate(data['documents']):
                print(f"[{i+1}] {doc}")
                print(f"    Meta: {data['metadatas'][i]}")
        else:
            print("Collection is empty.")
            
    except Exception as e:
        print(f"Error inspecting {dir_name}: {e}")
    print("------------------------------\n")

if __name__ == "__main__":
    # Check both potential directories
    inspect_chroma("chroma_ltm_db")
    inspect_chroma("chroma_db")
