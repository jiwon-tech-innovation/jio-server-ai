import sys
import os
import asyncio
# Ensure app module can be imported
sys.path.append(os.getcwd())

from app.schemas.intelligence import ClassifyRequest
from app.services import classifier

async def test_jarvis_scolding():
    print("=== [TEST] Jarvis Proactive Scolding ===")
    
    from app.schemas.intelligence import ClassifyRequest, InputMetrics, MediaInfo

    from app.schemas.intelligence import ClassifyRequest, InputMetrics, MediaInfo, SystemMetrics

    # Scenario 1: High CPU (Busy) -> Should NOT Scold/Talk
    print("\n1. Simulating High CPU (Busy compiling)...")
    req_busy = ClassifyRequest(
        active_window="VS Code",
        windows=["VS Code", "Chrome"],
        system_metrics=SystemMetrics(cpu_percent=90.0, volume_level=50),
        input_metrics=InputMetrics(keyboard={"kpm": 0}) 
    )
    resp_busy = await classifier.classify_content(req_busy)
    
    if resp_busy.message is None:
        print(">> PASS: JIAA kept silent due to High CPU.")
    else:
        print(f">> FAIL: JIAA talked: {resp_busy.message}")

    # Scenario 2: Long Uptime (Health Check)
    print("\n2. Simulating Long Uptime (Health Check)...")
    req_health = ClassifyRequest(
        active_window="VS Code",
        windows=["VS Code"],
        system_metrics=SystemMetrics(cpu_percent=10.0, uptime_seconds=3600), # 60 mins
        input_metrics=InputMetrics(keyboard={"kpm": 200})
    )
    resp_health = await classifier.classify_content(req_health)
    
    print(f"Jarvis Message: {resp_health.message}")
    if resp_health.message:
         print(">> PASS: JIAA sent a health reminder (Message content verified manually).")
    else:
         print(">> FAIL: No health check message.")
    
    return

    # Call classifier (Old Logic commented out)
    # try: ...

if __name__ == "__main__":
    asyncio.run(test_jarvis_scolding())
