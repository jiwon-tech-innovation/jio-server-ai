import asyncio
import sys

# Ensure /app is in path
sys.path.append("/app")

from app.services.memory_service import memory_service

async def main():
    print("--- [TEST] Chat Trigger Hook (MemoryService -> ReportService) ---")
    try:
        # Simulate Chat Trigger: "오늘 리포트 써줘" -> topic="Today Report"
        topic = "Today Report"
        print(f"Testing topic: '{topic}'")
        
        # This should call report_service.generate_daily_wrapped internally
        result = await memory_service.get_recent_summary_markdown(topic)
        
        print("\n=== Result (Should be Full Report) ===")
        print(result[:500] + "...") # Print first 500 chars
        
        if "내일의 행동" in result or "회고록" in result or "Plan" in result:
             print("\n✅ SUCCESS: Redirected to ReportService!")
        else:
             print("\n❌ FAILURE: returned standard memory summary.")
             
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
