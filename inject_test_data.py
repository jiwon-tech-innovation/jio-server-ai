
import asyncio
from app.core.influx import InfluxClientWrapper
from app.core.config import get_settings
from datetime import datetime, timedelta
import random
import os

settings = get_settings()

# 설정
BUCKET = "sensor_data" # settings.INFLUXDB_BUCKET might be env var, but let's hardcode safely if needed. Or use settings.
# Actually settings uses env vars.
# Let's use the env vars from the running pod if possible, but the script runs as __main__.
# We need to ensure we get a write_api.

async def inject_data():
    print("🚀 Injecting Test Data for 'wonji05227@gmail.com'...")
    write_api = InfluxClientWrapper.get_write_api()
    bucket = settings.INFLUXDB_BUCKET
    org = settings.INFLUXDB_ORG

    points = []
    
    # Generate data for the last 6 hours
    now = datetime.utcnow()
    
    activities = [
        {"category": "STUDY", "app": "VSCode", "duration": 30},
        {"category": "PLAY", "app": "League of Legends", "duration": 45},
        {"category": "STUDY", "app": "Chrome (StackOverflow)", "duration": 15},
        {"category": "PLAY", "app": "YouTube", "duration": 20},
        {"category": "STUDY", "app": "Terminal", "duration": 60},
    ]

    for i, act in enumerate(activities):
        time_offset = now - timedelta(hours=6-i)
        from influxdb_client import Point

        p = Point("user_activity_v2") \
            .tag("user_id", "wonji05227@gmail.com") \
            .tag("category", act["category"]) \
            .tag("type", "APP_USAGE") \
            .field("action_detail", act["app"]) \
            .field("duration_min", int(act["duration"])) \
            .time(time_offset)
        
        points.append(p)

    # Add Quiz Data
    p_quiz = Point("user_activity_v2") \
        .tag("user_id", "wonji05227@gmail.com") \
        .tag("type", "QUIZ") \
        .field("action_detail", "Python Decorators") \
        .field("score", 85) \
        .field("wrong_answers", "['Closure', 'Scope']") \
        .time(now - timedelta(minutes=30))
    points.append(p_quiz)

    print(f"📝 Preparing {len(points)} points...")
    
    try:
        # Sync write
        write_api.write(bucket=bucket, org=org, record=points)
        print("✅ Injection Successful!")
    except Exception as e:
        print(f"❌ Injection Failed: {e}")
    finally:
        write_api.close()

if __name__ == "__main__":
    asyncio.run(inject_data())
