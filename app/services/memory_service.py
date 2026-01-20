from datetime import datetime
from app.core.memory import get_vector_store, get_long_term_store
from langchain_core.documents import Document
from app.core.llm import get_llm, HAIKU_MODEL_ID, SONNET_MODEL_ID
from langchain_core.prompts import PromptTemplate
from app.core.config import get_settings
from langchain_community.vectorstores import Redis
from app.services.statistic_service import statistic_service

settings = get_settings()

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
        
        # In-Memory Last Interaction Tracker (Reset on Server Restart is fine)
        self.last_interaction_time = datetime.now()

    def update_interaction_time(self):
        self.last_interaction_time = datetime.now()

    def get_silence_duration_minutes(self) -> float:
        delta = datetime.now() - self.last_interaction_time
        return delta.total_seconds() / 60.0

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

    def save_violation(self, content: str, source: str = "Unknown", user_id: str = "dev1"):
        self._save_event(
            content=f"User was caught playing/slacking: {content}",
            event_type="VIOLATION",
            metadata={"source": source, "category": "PLAY", "user_id": user_id}
        )
        # [TRUST SCORE] Slacking reduces trust
        self.update_trust_score(user_id, -5)

    def save_achievement(self, content: str, user_id: str = "dev1"):
        self._save_event(
            content=f"User was studying: {content}",
            event_type="ACHIEVEMENT",
            metadata={"category": "STUDY", "user_id": user_id}
        )
        # [TRUST SCORE] Studying increases trust
        self.update_trust_score(user_id, 2)

    def save_quiz_result(self, topic: str, score: int, max_score: int, user_id: str = "dev1"):
        """
        Saves quiz performance to STM.
        """
        percent = (score / max_score) * 100
        content = f"Quiz Result: {topic} - {score}/{max_score} ({percent:.1f}%)"
        self._save_event(
            content=content,
            event_type="QUIZ",
            metadata={"topic": topic, "score": score, "max_score": max_score, "category": "STUDY", "user_id": user_id}
        )
        # [TRUST SCORE] High score boosts trust significantly
        if percent >= 80:
            self.update_trust_score(user_id, 5)
        elif percent < 50:
             self.update_trust_score(user_id, -2) # Penalty for poor performance despite "studying"

    def _get_redis_client(self):
        # Helper to get a direct Redis client
        import redis
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )

    def get_trust_score(self, user_id: str = "dev1") -> int:
        """
        Retrieves the persistent Trust Score from Redis.
        Default: 100 (Max Trust).
        """
        try:
            key = f"user:{user_id}:trust_score"
            client = self._get_redis_client()
            val = client.get(key)
            client.close()
            
            if val is None:
                # [DEFAULT] New users start at 50 (Mesugaki Mode)
                print(f"DEBUG: Trust Score for {user_id} is None, returning 50")
                return 50
            
            score = int(float(val)) # float safe
            print(f"DEBUG: Retrieved Trust Score for {user_id}: {score}")
            return score
        except Exception as e:
            print(f"Trust Score Get Error: {e}")
            return 50

    def update_trust_score(self, user_id: str, delta: int):
        """
        Updates the Trust Score. Clamped between 0 and 100.
        """
        try:
            current = self.get_trust_score(user_id)
            new_score = max(0, min(100, current + delta))
            
            key = f"user:{user_id}:trust_score"
            client = self._get_redis_client()
            client.set(key, new_score)
            client.close()
            print(f"📉 [Trust] Score Updated: {current} -> {new_score} (Delta: {delta})")
            
        except Exception as e:
            print(f"Trust Score Update Error: {e}")
    
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

    def get_daily_quiz_results(self, date_str: str = None) -> list[str]:
        """
        Retrieves ONLY quiz results for the day.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        results = []
        try:
            # Search specifically for Quiz events
            docs = self.stm.similarity_search("Quiz Result", k=20)
            for doc in docs:
                ts = doc.metadata.get("timestamp", "")
                event_type = doc.metadata.get("event_type", "")
                
                if ts.startswith(date_str) and event_type == "QUIZ":
                     results.append(f"{doc.page_content}")
            
            return results
        except Exception as e:
            print(f"Quiz Fetch Error: {e}")
            return []

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

    async def _generate_daily_report_text(self, user_id: str = "dev1") -> str:
        """
        Internal helper: Generates the 'Daily TIL' report string using broad search & LLM.
        Refactored for Data Trinity: Uses InfluxDB for Ground Truth.
        """
        # 1. Fetch Ground Truth from InfluxDB (Activity Timeline)
        timeline = await statistic_service.get_daily_timeline(user_id)
        timeline_text = "\n".join(timeline) if timeline else "No activity recorded in InfluxDB."

        # 2. Fetch Quiz Logs (Data Trinity)
        quiz_logs = await statistic_service.get_daily_quiz_logs(user_id)
        quiz_text = ""
        if quiz_logs:
            quiz_text = "### Quiz Session\n"
            for log in quiz_logs:
                quiz_text += f"- Topic: {log['topic']}\n  Score: {log['score']}\n  Wrong Answers: {log['wrong_answers']}\n"
        else:
            quiz_text = "No quiz taken today."

        # 3. Fetch Qualitative Context from STM (Redis)
        queries = ["User studying coding", "User playing games", "User conversation", "System violation log"]
        all_docs = []
        seen_ids = set()

        for q in queries:
            docs = self.stm.similarity_search(q, k=10) # Reduced k since we have Influx
            for d in docs:
                if d.page_content not in seen_ids:
                    all_docs.append(d)
                    seen_ids.add(d.page_content)

        stm_text = "\n".join([f"- {d.page_content} (Meta: {d.metadata})" for d in all_docs])
        
        # 4. Summarize via LLM (TIL Format)
        llm = get_llm(model_id=HAIKU_MODEL_ID)
        prompt = f"""
        You are a Tech Blogger Bot.
        Write a **"Daily TIL (Today I Learned)"** report for the user.
        
        **Data Sources**:
        1. **Activity Timeline** (InfluxDB): Reliable chronological log of what happened.
        2. **Quiz Results** (InfluxDB): Exact score and wrong answers (Use this for coaching!).
        3. **Context Fragments** (Short-Term Memory): Qualitative details of conversations.

        **Timeline**:
        {timeline_text}

        **Quiz Results**:
        {quiz_text}

        **Context Memory**:
        {stm_text}
        
        **Requirements**:
        1. **Chronological Flow**: Based on the Timeline.
        2. **Coaching**: If they took a quiz, analyze their wrong answers and give specific advice.
        3. **Honesty**: Mention if they slacked off (check timeline/context).
        4. **Tone**: witty, slightly critical but helpful. Use Markdown.

        **Output Format**:
        # 📅 Daily Report ({datetime.now().strftime("%Y-%m-%d")})
        ## 📝 3-Line Summary
        1. 
        ...
        ## 🧠 Knowledge Gained (Quiz Analysis)
        ...
        """
        summary = await llm.ainvoke(prompt)
        return summary.content

    async def consolidate_memory(self, user_id: str = "dev1"):
        """
        [Sleep Routine]
        1. Generates Daily Report.
        2. Saves to LTM.
        3. Clears STM.
        """
        if not self.ltm:
            print("ERROR: LTM (Postgres) is not available. Skipping consolidation.")
            return

        print("🔄 [Memory] Starting Daily Consolidation...")
        summary_text = await self._generate_daily_report_text(user_id=user_id)
        
        # [ARCHITECTURAL ALIGNMENT]
        # Redis is volatile/short-term. PGVector is permanent.
        # We must log the final "Trust Score" of the day to LTM so it persists in history.
        current_trust = self.get_trust_score(user_id)
        summary_text += f"\n\n**End-of-Day Trust Score**: {current_trust}/100"
        
        print(f"✅ [Memory] Daily Summary Generated:\n{summary_text}")

        # 3. Save to LTM
        try:
            self.ltm.add_texts(
                [summary_text], 
                metadatas=[{"event_type": "DAILY_SUMMARY", "date": datetime.now().strftime("%Y-%m-%d"), "user_id": user_id}]
            )
            print("✅ [Memory] Saved summary to LTM (PGVector).")
            
            try:
                # Construct Redis URL safely
                redis_password = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
                redis_url = f"redis://{redis_password}{settings.REDIS_HOST}:{settings.REDIS_PORT}"
                
                # Drop Index using Class Method or Instance wrapper
                # LangChain Redis.drop_index is a static/class method
                Redis.drop_index(index_name="jiaa_memory", delete_documents=True, redis_url=redis_url)
                print("✅ [Memory] STM (Redis) Flushed.")
                
                # Re-init index immediately
                self.stm = get_vector_store()
                self._save_event("Genesis Block: Memory Consolidate & Reset.", "SYSTEM_RESET")
                
            except Exception as e:
                 print(f"WARNING: STM Flush failed (Manual deletion might be required): {e}")

        except Exception as e:
            print(f"ERROR: Consolidation Failed: {e}")

    async def get_recent_summary_markdown(self, topic: str, user_id: str = "dev1") -> str:
        """
        Generates a Markdown summary for a specific topic based on recent memories.
        Used for 'Smart Note' feature.
        """
        # [LOGIC HOOK] If topic is "Today" or "Daily", use the robust TIL generator
        lower_topic = topic.lower()
        if any(k in lower_topic for k in ["today", "daily", "오늘", "하루", "메모리", "report", "til", "퀴즈", "quiz", "summary"]):
            print(f"DEBUG: Redirecting '{topic}' to Daily Report Generator (Triangulation).")
            # [Fix] Use ReportService for Triangulation (Plan vs Actual vs Said)
            # Local import to avoid circular dependency
            from app.services.report_service import report_service
            # Forward user_id to ReportService (Fixed)
            return await report_service.generate_daily_wrapped(user_id=user_id)

        context_docs = self.stm.similarity_search(topic, k=10)
        if not context_docs:
            return f"# {topic}\n\n(No recent context found for this topic.)"
        
        context_text = "\n".join([f"- {d.page_content}" for d in context_docs])
        
        # [User Request] Ensure writing tasks use Sonnet (High Intelligence)
        llm = get_llm(model_id=SONNET_MODEL_ID, temperature=0.7)
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
