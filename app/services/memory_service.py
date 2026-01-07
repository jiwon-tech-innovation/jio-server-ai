from datetime import datetime
from app.core.memory import get_vector_store, get_long_term_store
from langchain_core.documents import Document
from app.core.llm import get_llm, HAIKU_MODEL_ID
from langchain_core.prompts import PromptTemplate

class MemoryService:
    def __init__(self):
        # STM: Short-Term Memory (Redis)
        self.stm = get_vector_store()
        # LTM: Long-Term Memory (PGVector)
        self.ltm = get_long_term_store()
        
        # [INIT CHECK] Ensure Redis Index Exists
        try:
            self.stm.similarity_search("genesis", k=1)
        except Exception as e:
            if "No such index" in str(e):
                print("DEBUG: Redis Index not found. Creating Genesis Block...")
                self._save_event("Genesis Block: Memory Initialized.", "SYSTEM_INIT")
            else:
                print(f"WARNING: Unknown Redis Error during init: {e}")

    def _save_event(self, content: str, event_type: str, metadata: dict = None):
        """
        Saves event to Short-Term Memory (Redis).
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

    def get_daily_activities(self, date_str: str = None) -> list[str]:
        """
        Retrieves all activity logs for a specific date (default: today).
        Returns a list of strings suitable for the blog post.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        print(f"DEBUG: Fetching activities for {date_str}...")
        
        # In a real vector store, we should use metadata filter: {"timestamp": ...}
        # But since timestamp is ISO format, partial match might be tricky in Chroma simple filter.
        # We will fetch 'k=100' most recent and filter in Python.
        
        activities = []
        try:
            # Broad search to get recent logs
            today_docs = self.stm.similarity_search("User study and play log", k=50)
            
            for doc in today_docs:
                # Timestamp format: 2026-01-04T...
                ts = doc.metadata.get("timestamp", "")
                if ts.startswith(date_str):
                    # Format: "[14:30] Content (Category)"
                    time_part = ts[11:16] # HH:MM
                    category = doc.metadata.get("category", "General")
                    activities.append(f"[{time_part}] {doc.page_content} ({category})")
                    
            # Sort by time just in case
            activities.sort()
            
        except Exception as e:
            print(f"STM Fetch Error: {e}")
            return ["(기록을 불러오는 중 에러가 발생했습니다.)"]
            
        if not activities:
            return ["(오늘의 특별한 활동 기록이 없습니다. 숨쉬기 운동 정도?)"]
            
        return activities

    async def consolidate_memory(self):
        """
        [Sleep Routine]
        1. Reads all STM events (Redis).
        2. Summarizes them using LLM.
        3. Saves summary to LTM (PGVector).
        4. Clears STM.
        """
        if not self.ltm:
            print("ERROR: LTM (Postgres) is not available. Skipping consolidation.")
            return

    async def _generate_daily_report_text(self) -> str:
        """
        Internal helper: Generates the 'Daily TIL' report string using broad search & LLM.
        """
        # 1. Fetch recent events with broader queries
        queries = ["User studying coding", "User playing games", "User conversation", "System violation log"]
        all_docs = []
        seen_ids = set()

        for q in queries:
            docs = self.stm.similarity_search(q, k=20)
            for d in docs:
                if d.page_content not in seen_ids:
                    all_docs.append(d)
                    seen_ids.add(d.page_content)

        if not all_docs:
            return "# Daily Report\nNo significant activity recorded today."

        log_text = "\n".join([f"- {d.page_content} (Meta: {d.metadata})" for d in all_docs])
        
        # 2. Summarize via LLM (TIL Format)
        llm = get_llm(model_id=HAIKU_MODEL_ID)
        prompt = f"""
        You are a Tech Blogger Bot.
        Based on the user's activity logs below, write a **"Daily TIL (Today I Learned)"** report.
        
        **Requirements**:
        1. **Chronological Flow**: What did they do from start to finish?
        2. **Honesty**: Mention if they slacked off (played games) vs studied.
        3. **Technical Details**: If they studied coding, mention specific topics.
        4. **Tone**: witty and slightly critical (if they played too much).

        **Logs**:
        {log_text}
        
        **Output Format**:
        # 📅 Daily Report ({datetime.now().strftime("%Y-%m-%d")})
        ## 📝 3-Line Summary
        1. 
        2. 
        3. 

        ## ⏱️ Timeline Analysis
        - (Reconstruct timeline based on logs)

        ## 💡 Key Learnings (or Excuses)
        - 
        """
        summary = await llm.ainvoke(prompt)
        return summary.content

    async def consolidate_memory(self):
        """
        [Sleep Routine]
        1. Generates Daily Report.
        2. Saves to LTM.
        3. Clears STM.
        """
        if not self.ltm:
            print("ERROR: LTM (Postgres) is not available. Skipping consolidation.")
            return

        summary_text = await self._generate_daily_report_text()
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

    async def get_recent_summary_markdown(self, topic: str) -> str:
        """
        Generates a Markdown summary for a specific topic based on recent memories.
        Used for 'Smart Note' feature.
        """
        # [LOGIC HOOK] If topic is "Today" or "Daily", use the robust TIL generator
        lower_topic = topic.lower()
        if any(k in lower_topic for k in ["today", "daily", "오늘", "하루", "메모리", "report", "til"]):
            print(f"DEBUG: Redirecting '{topic}' to Daily Report Generator.")
            return await self._generate_daily_report_text()

        context_docs = self.stm.similarity_search(topic, k=10)
        if not context_docs:
            return f"# {topic}\n\n(No recent context found for this topic.)"
        
        context_text = "\n".join([f"- {d.page_content}" for d in context_docs])
        
        llm = get_llm(model_id=HAIKU_MODEL_ID)
        prompt = f"""
        You are a helpful technical assistant.
        Write a clean, structured Markdown note about the topic: "{topic}".
        Use the provided context logs/memory to fill in details.
        
        Context:
        {context_text}
        
        Output Format:
        # [Topic]
        ## Summary
        ## Key Points
        - ...
        """
        
        response = await llm.ainvoke(prompt)
        return response.content

memory_service = MemoryService()
