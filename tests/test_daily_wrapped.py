import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.append(".")

# Mock Settings
from app.core.config import Settings
mock_settings = Settings()
mock_settings.BEDROCK_REGION = "us-east-1"
mock_settings.AWS_REGION = "us-east-1"
mock_settings.INFLUXDB_BUCKET = "test"
mock_settings.INFLUXDB_ORG = "test"

async def test_daily_wrapped():
    print("=== Testing Daily Wrapped (Triangulation) ===")
    
    # Ensure module is loaded
    import app.services.report_service

    # Needs many mocks: Calendar, Influx(Statistic), Memory, Bedrock
    with patch("app.services.report_service.calendar_service") as mock_cal, \
         patch("app.services.report_service.statistic_service") as mock_stat, \
         patch("app.services.report_service.memory_service") as mock_mem, \
         patch("app.services.report_service.get_llm") as mock_get_llm:
         
        # 1. Mock Calendar (PLAN)
        mock_cal.get_todays_plan.return_value = [
            {"summary": "Algorithm Study", "start": "14:00", "end": "16:00"},
            {"summary": "Project Dev", "start": "17:00", "end": "19:00"}
        ]
        
        # 2. Mock Influx (ACTUAL)
        # 14:00-16:00 -> Played LoL (Failure)
        # 17:00-19:00 -> VSCode (Success)
        mock_stat.get_daily_timeline = AsyncMock(return_value=[
            "[14:00] Played League of Legends (PLAY)",
            "[15:00] Played League of Legends (PLAY)",
            "[17:00] User active in VSCode (STUDY)",
            "[18:00] User active in VSCode (STUDY)"
        ])
        
        # 3. Mock Memory (SAID)
        mock_mem.get_daily_activities.return_value = [
            "User said: 'I will definitely study algorithm today.'",
            "User said: 'I am so productive.'"
        ]
        
        # 4. Mock LLM
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(content="""
# 📅 Daily Wrapped: Failed
## Plan vs Actual
- **Algorithm Study**: FAILED. You played LoL instead.
- **Project Dev**: PASSED. Good job using VSCode.
## The Lie
You said "I will definitely study algorithm", but the logs show you entered the Summoner's Rift.
## Grade: C-
""")
        mock_get_llm.return_value = mock_llm_instance
        
        # Run
        from app.services.report_service import report_service
        report = await report_service.generate_daily_wrapped("dev1")
        
        print("\n--- Generated Report ---")
        print(report)
        print("------------------------")
        
        # Assertions
        mock_cal.get_todays_plan.assert_called()
        print("[✔] Calendar checked.")
        mock_stat.get_daily_timeline.assert_called()
        print("[✔] InfluxDB Logs checked.")
        if "FAILED" in report:
            print("[✔] Discrepancy detected (Mock).")
        else:
             print("[X] Discrepancy logic might be weak.")

if __name__ == "__main__":
    asyncio.run(test_daily_wrapped())
