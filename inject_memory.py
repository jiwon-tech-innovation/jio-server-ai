import sys
import os
from datetime import datetime, timedelta

# Add parent dir to path to find 'app' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.memory import get_embeddings
from langchain_community.vectorstores import Chroma

def inject_scenario():
    print("🚀 Starting Memory Injection Scenario...")
    
    # Initialize LTM (Chroma)
    persist_directory = os.path.join(os.getcwd(), "chroma_ltm_db")
    print(f"📂 Chroma DB Path: {persist_directory}")
    
    # Must use same embedding function as app
    embedding_fn = get_embeddings()
    
    ltm = Chroma(
        collection_name="jiaa_long_term_memory",
        embedding_function=embedding_fn,
        persist_directory=persist_directory
    )
    
    # Define Timeline
    today = datetime.now()
    dates = {
        "d7": (today - timedelta(days=7)).strftime("%Y-%m-%d"),
        "d6": (today - timedelta(days=6)).strftime("%Y-%m-%d"),
        "d5": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
        "d4": (today - timedelta(days=4)).strftime("%Y-%m-%d"),
        "d3": (today - timedelta(days=3)).strftime("%Y-%m-%d"),
    }
    
    # Scenario Data
    memories = [
        {
            "date": dates["d7"],
            "content": "User set a goal to MASTER Spring Boot. However, they failed immediately and played League of Legends for 3 hours instead. They were scolded but showed no progress.",
            "type": "DAILY_SUMMARY"
        },
        {
            "date": dates["d6"],
            "content": "User studied JPA. They struggled with Postgres authentication errors (env config mismatch) for 3 hours. They tried their best to understand.",
            "type": "DAILY_SUMMARY"
        },
        {
            "date": dates["d5"],
            "content": "User relapsed into gaming. Played PUBG (Battlegrounds) for 6 hours straight. Complete waste of time.",
            "type": "DAILY_SUMMARY"
        },
        {
            "date": dates["d4"],
            "content": "User studied a little bit of Java syntax. Very minor progress.",
            "type": "DAILY_SUMMARY"
        }
    ]
    
    print(f"📦 Injecting {len(memories)} memories...")
    
    ids = ltm.add_texts(
        texts=[m["content"] for m in memories],
        metadatas=[{"event_type": m["type"], "date": m["date"]} for m in memories]
    )
    
    print(f"✅ Injection Complete! IDs: {ids}")
    print("Verification: You can now ask the AI 'Did I study well last week?'")

if __name__ == "__main__":
    inject_scenario()
