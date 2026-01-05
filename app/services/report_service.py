from datetime import datetime
from app.services.calendar_service import calendar_service
from app.services.statistic_service import statistic_service
from app.services.memory_service import memory_service
from app.core.llm import get_llm, HAIKU_MODEL_ID
from langchain_core.prompts import PromptTemplate

class ReportService:
    def __init__(self):
        self.llm = get_llm(model_id=HAIKU_MODEL_ID)

    async def generate_daily_wrapped(self, user_id: str) -> str:
        """
        Generates a "Daily Wrapped" report by triangulating Plan vs Actual vs Said.
        """
        # 1. Fetch Plans (Calendar)
        plans = calendar_service.get_todays_plan()
        plan_str = "\n".join([f"- [{p['start']}~{p['end']}] {p['summary']}" for p in plans])
        if not plan_str: plan_str = "(No plans recorded)"

        # 2. Fetch Actuals (InfluxDB Timeline)
        timeline = await statistic_service.get_daily_timeline(user_id)
        actual_str = "\n".join(timeline)
        if not actual_str: actual_str = "(No significant activity logs)"

        # 3. Fetch Said (Vector Memory - Daily Summary)
        # We reuse get_daily_activities from MemoryService, but it searches STM.
        # It's close enough to "What I did/said today".
        # Better: Search specifically for "Promise" or "Plan" keywords if we want "Said".
        said_list = memory_service.get_daily_activities()
        said_str = "\n".join(said_list)

        # 4. LLM Generation
        prompt = f"""
You are "Alpine", the critical code reviewer and life coach.
Write a "Daily Wrapped" (Daily Retrospective) for the user "Dev 1".

### DATA SOURCES
1. [PLAN] What they planned (Google Calendar):
{plan_str}

2. [ACTUAL] What they did (System Logs):
{actual_str}

3. [SAID] What they claimed/chatted (Chat Logs):
{said_str}

### INSTRUCTIONS
- Compare [PLAN] vs [ACTUAL]. DO NOT trust [SAID] if it contradicts [ACTUAL].
- Detect discrepancies: e.g., Plan="Study" but Actual="LoL".
- Tone: Strict, Analytical, Evidence-Based. "Tsundere Meshgaki" flavor is optional here; focus on "Fact Bombing".
- Format: Markdown.
  - **Summary**: Grade the day (A/B/C/F).
  - **Plan vs Actual**: Detailed comparison table or bullet points.
  - **The Lie**: Did they lie about studying?
  - **Action Item**: What to fix tomorrow.

Write the report in **Korean**.
"""
        response = self.llm.invoke(prompt)
        return response.content

report_service = ReportService()
