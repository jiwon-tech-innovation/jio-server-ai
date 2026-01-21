
import asyncio
from datetime import datetime, timedelta
from app.services.memory_service import memory_service
from app.core.config import get_settings
from app.core.influx import InfluxClientWrapper

# Target User
USER_ID = "wonji05227@gmail.com"
settings = get_settings()

async def inject_trust_history():
    print(f"🚀 Injecting 5-Day Trust History for {USER_ID}...")
    
    # 1. Define 5-Day Scenario
    # Day 1: High Trust (Study Hard)
    # Day 2: High Trust (Study)
    # Day 3: Low Trust (Game Binge)
    # Day 4: Mid Trust (Recovering)
    # Day 5 (Today): current data
    
    scenarios = [
        {"day_offset": 5, "trust": 90, "summary": "User studied effectively. High focus.", "activities": [("STUDY", "VSCode", 120), ("STUDY", "Docs", 30)]},
        {"day_offset": 4, "trust": 95, "summary": "Excellent performance. Aced the quiz.", "activities": [("STUDY", "VSCode", 150), ("STUDY", "Terminal", 60)]},
        {"day_offset": 3, "trust": 30, "summary": "Disappointing. Played games all day.", "activities": [("PLAY", "League of Legends", 180), ("PLAY", "YouTube", 60)]},
        {"day_offset": 2, "trust": 50, "summary": "Trying to recover but still distracted.", "activities": [("STUDY", "VSCode", 45), ("PLAY", "YouTube", 45)]},
        {"day_offset": 1, "trust": 75, "summary": "Better focus today. Good job.", "activities": [("STUDY", "VSCode", 90), ("STUDY", "Postman", 30)]},
    ]

    # 2. Inject LTM Summaries (PGVector)
    print("💾 Injecting LTM Daily Summaries...")
    for s in scenarios:
        date_str = (datetime.now() - timedelta(days=s["day_offset"])).strftime("%Y-%m-%d")
        
        summary_content = f"""# 📅 Daily Check ({date_str})
## 📝 Summary
{s["summary"]}

**End-of-Day Trust Score**: {s["trust"]}/100
"""
        try:
            memory_service.ltm.add_texts(
                [summary_content],
                metadatas=[{"event_type": "DAILY_SUMMARY", "date": date_str, "user_id": USER_ID}]
            )
            print(f"   - Stored LTM for {date_str} (Trust: {s['trust']})")
        except Exception as e:
            print(f"   - ⚠️ Failed to store LTM for {date_str}: {e}")

    # 3. Inject InfluxDB Activities (V2)
    print("📈 Injecting InfluxDB Activities (V2)...")
    write_api = InfluxClientWrapper.get_write_api()
    bucket = settings.INFLUXDB_BUCKET
    org = settings.INFLUXDB_ORG
    
    points = []
    from influxdb_client import Point
    
    now = datetime.utcnow()

    for s in scenarios:
        day_date = now - timedelta(days=s["day_offset"])
        start_hour = 10 # 10 AM
        
        for cat, app, duration in s["activities"]:
            p = Point("user_activity_v2") \
                .tag("user_id", USER_ID) \
                .tag("category", cat) \
                .tag("type", "APP_USAGE") \
                .field("action_detail", app) \
                .field("duration_min", int(duration)) \
                .time(day_date.replace(hour=start_hour, minute=0, second=0))
            points.append(p)
            start_hour += 2 # Spread out

    try:
        write_api.write(bucket=bucket, org=org, record=points)
        print(f"   - Injected {len(points)} activity points.")
    except Exception as e:
        print(f"   - ❌ Influx Injection Failed: {e}")
    finally:
        write_api.close()

    # 4. Set CURRENT Trust Score (Redis)
    # Let's say today is Day 0, based on yesterday (Day 1) it was 75.
    # We set it to 80 to start fresh.
    print("📉 Setting Current Trust Score...")
    try:
        # Use direct redis update via memory_service helper logic
        key = f"user:{USER_ID}:trust_score"
        client = memory_service._get_redis_client()
        client.set(key, 80)
        client.close()
        print(f"   - Set Redis {key} to 80")
    except Exception as e:
        print(f"   - ❌ Redis Update Failed: {e}")

    print("✅ History Injection Complete!")

if __name__ == "__main__":
    asyncio.run(inject_trust_history())
