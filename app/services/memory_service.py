from datetime import datetime
from app.core.memory import get_vector_store, get_long_term_store
from langchain_core.documents import Document
from app.core.llm import get_llm, HAIKU_MODEL_ID
from langchain_core.prompts import PromptTemplate
from app.core.redis_client import get_redis_client
import json

class MemoryService:
    def __init__(self):
        # STM: Short-Term Memory (Redis for Chat)
        self.redis = get_redis_client()
        
        # Event Memory: Significant Events (Chroma)
        self.event_store = get_vector_store()
        
        # LTM: Long-Term Memory (PGVector)
        self.ltm = get_long_term_store()

    async def add_chat_log(self, user_id: str, role: str, content: str):
        """
        Saves chat log to Redis List (Sliding Window).
        Format: "Role: Content"
        """
        key = f"chat_history:{user_id}"
        entry = json.dumps({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        
        try:
            # Push to right (newest)
            await self.redis.rpush(key, entry)
            # Trim to keep last 20 turns (User + AI = 10 pairs)
            await self.redis.ltrim(key, -20, -1)
        except Exception as e:
            print(f"Redis Push Error: {e}")

    async def get_recent_chat(self, user_id: str, k: int = 10) -> str:
        """
        Retrieves recent k chat logs from Redis.
        """
        key = f"chat_history:{user_id}"
        try:
            # Get last k items
            logs = await self.redis.lrange(key, -k, -1)
            formatted_logs = []
            for log in logs:
                data = json.loads(log)
                formatted_logs.append(f"{data['role']}: {data['content']}")
            return "\n".join(formatted_logs)
        except Exception as e:
            print(f"Redis Fetch Error: {e}")
            return ""

    def _save_event(self, content: str, event_type: str, metadata: dict = None):
        """
        Saves significant EVENT to VectorDB (Chroma).
        NOT for casual chat.
        """
        if metadata is None: metadata = {}
        timestamp = datetime.now().isoformat()
        metadata.update({"event_type": event_type, "timestamp": timestamp})
        
        doc = Document(page_content=content, metadata=metadata)
        self.event_store.add_documents([doc])
        print(f"DEBUG: Event Saved [{event_type}] {content}")

    def save_violation(self, content: str, source: str = "Unknown"):
        self._save_event(
            content=f"User was caught playing/slacking: {content}",
            event_type="VIOLATION",
            metadata={"source": source, "category": "PLAY"}
        )

    def save_achievement(self, content: str):
        self._save_event(
            content=f"User was studying: {content}",
            event_type="ACHIEVEMENT",
            metadata={"category": "STUDY"}
        )
    
    async def get_user_context(self, user_id: str, query: str) -> str:
        """
        Retrieves context from:
        1. Redis (Recent Chat)
        2. Chroma (Recent Events)
        3. LTM (Deep History)
        """
        context = "=== Memory Context ===\n"
        
        # 1. Redis (Chat History) -> STM
        chat_history = await self.get_recent_chat(user_id, k=10)
        if chat_history:
            context += "[Recent Conversation (STM)]\n"
            context += chat_history + "\n"
        
        # 2. Chroma (Recent Events) -> Episodic
        try:
            # Search for events related to the query OR just recent events?
            # Query-based is better for relevance.
            event_docs = self.event_store.similarity_search(query, k=2)
            if event_docs:
                context += "\n[Recent Events (Episodic)]\n"
                for doc in event_docs:
                    ts = doc.metadata.get("timestamp", "")[:16].replace("T", " ")
                    context += f"- [{ts}] {doc.page_content}\n"
        except Exception as e:
            print(f"Event Search Error: {e}")

        # 3. LTM Search (Deep History)
        if self.ltm:
            try:
                ltm_docs = self.ltm.similarity_search(query, k=2)
                if ltm_docs:
                    context += "\n[Long-Term History & Persona]\n"
                    for doc in ltm_docs:
                        context += f"- {doc.page_content}\n"
            except Exception as e:
                print(f"LTM Search Error: {e}")
        
        context += "======================\n"
        return context

    def get_daily_activities(self, date_str: str = None) -> list[str]:
        """
        Retrieves activity logs for a specific date from Chroma (Event Store).
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        print(f"DEBUG: Fetching activities for {date_str}...")
        
        activities = []
        try:
            # Broad search in Event Store
            today_docs = self.event_store.similarity_search("User study and play log", k=50)
            
            for doc in today_docs:
                ts = doc.metadata.get("timestamp", "")
                if ts.startswith(date_str):
                    time_part = ts[11:16]
                    category = doc.metadata.get("category", "General")
                    activities.append(f"[{time_part}] {doc.page_content} ({category})")
                    
            activities.sort()
            
        except Exception as e:
            print(f"Event Fetch Error: {e}")
            return ["(Error loading activities)"]
            
        if not activities:
            return ["(No special activities recorded today.)"]
            
        return activities

    async def consolidate_memory(self):
        """
        [Sleep Routine]
        Summarizes Chroma Events -> LTM.
        (Redis Chat History is strictly ephemeral and acts as sliding window buffer, maybe summarize it too?)
        """
        if not self.ltm:
            return

        # Fetch Events
        events = self.event_store.similarity_search("User activity log", k=50)
        
        # Ideally we should also fetch today's chat history from Redis if we want to summarize conversation?
        # extra_chats = await self.get_recent_chat("dev1", k=50) 
        
        if not events:
            return

        log_text = "\n".join([f"- {d.page_content}" for d in events])
        
        llm = get_llm(model_id=HAIKU_MODEL_ID)
        prompt = f"""
        Summarize the following user activity logs into a concise diary entry.
        Focus on: What did they study? Did they slack off?
        Format: "User [Action summary]. Notable: [Details]."
        
        Logs:
        {log_text}
        """
        summary = await llm.ainvoke(prompt)
        summary_text = summary.content
        print(f"DEBUG: Daily Summary: {summary_text}")

        try:
            self.ltm.add_texts(
                [summary_text], 
                metadatas=[{"event_type": "DAILY_SUMMARY", "date": datetime.now().strftime("%Y-%m-%d")}]
            )
            print("DEBUG: Saved summary to LTM.")
        except Exception as e:
            print(f"ERROR: Consolidation Failed: {e}")

memory_service = MemoryService()
