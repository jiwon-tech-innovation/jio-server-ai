from datetime import datetime
from app.core.memory import get_vector_store, get_long_term_store
from langchain_core.documents import Document
from app.core.llm import get_llm, HAIKU_MODEL_ID
from langchain_core.prompts import PromptTemplate

class MemoryService:
    def __init__(self):
        # STM: Short-Term Memory (Chroma)
        self.stm = get_vector_store()
        # LTM: Long-Term Memory (PGVector)
        self.ltm = get_long_term_store()

    def _save_event(self, content: str, event_type: str, metadata: dict = None):
        """
        Saves event to Short-Term Memory (Chroma).
        """
        if metadata is None: metadata = {}
        timestamp = datetime.now().isoformat()
        metadata.update({"event_type": event_type, "timestamp": timestamp})
        
        doc = Document(page_content=content, metadata=metadata)
        self.stm.add_documents([doc])
        print(f"DEBUG: STM Saved [{event_type}] {content}")

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
    
    def get_user_context(self, query: str) -> str:
        """
        Retrieves context from BOTH Short-Term (STM) and Long-Term (LTM).
        """
        context = "=== Memory Context ===\n"
        
        # 1. STM Search (Recent Context)
        try:
            stm_docs = self.stm.similarity_search(query, k=3)
            if stm_docs:
                context += "[Recent Short-Term Memories]\n"
                for doc in stm_docs:
                    ts = doc.metadata.get("timestamp", "")[:16].replace("T", " ")
                    context += f"- [{ts}] {doc.page_content}\n"
        except Exception as e:
            print(f"STM Search Error: {e}")

        # 2. LTM Search (Deep History)
        if self.ltm:
            try:
                ltm_docs = self.ltm.similarity_search(query, k=2)
                if ltm_docs:
                    context += "\n[Long-Term History & Persona]\n"
                    for doc in ltm_docs:
                        # LTM might store summaries, so just show content
                        context += f"- {doc.page_content}\n"
            except Exception as e:
                print(f"LTM Search Error: {e}") # Likely DB connection fail
        
        context += "======================\n"
        return context

    async def consolidate_memory(self):
        """
        [Sleep Routine]
        1. Reads all STM events (Chroma).
        2. Summarizes them using LLM.
        3. Saves summary to LTM (PGVector).
        4. Clears STM.
        """
        if not self.ltm:
            print("ERROR: LTM (Postgres) is not available. Skipping consolidation.")
            return

        # 1. Fetch recent events (Naive approach: get all by dummy query or logic)
        # Since Chroma doesn't support 'get all' easily without ID, we search broadly
        # For production, better to peek or query by date. 
        # Here we simulate by searching for generic terms covering everything.
        events = self.stm.similarity_search("User activity log", k=50) # Hacky fetch
        if not events:
            print("Consolidation: No recent memories found.")
            return

        log_text = "\n".join([f"- {d.page_content}" for d in events])
        
        # 2. Summarize via LLM
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

        # 3. Save to LTM
        try:
            self.ltm.add_texts(
                [summary_text], 
                metadatas=[{"event_type": "DAILY_SUMMARY", "date": datetime.now().strftime("%Y-%m-%d")}]
            )
            print("DEBUG: Saved summary to LTM.")
            
            # 4. Flush STM (In Chroma file mode, difficult to delete all without ID)
            # For now, we assume 'reset' or just keep appending until file rotation.
            # Ideally: self.stm.delete_collection() -> re-init
            print("WARNING: STM flush not fully implemented for Chroma (File Mode).")
            
        except Exception as e:
            print(f"ERROR: Consolidation Failed: {e}")

memory_service = MemoryService()
