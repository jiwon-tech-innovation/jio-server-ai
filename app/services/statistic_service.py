from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import pytz
from app.core.influx import InfluxClientWrapper
from app.core.config import get_settings

settings = get_settings()

class StatisticService:
    # Removed get_play_ratio (SQL version) as we are moving to Influx
    
    async def get_recent_summary(self, user_id: str, days: int = 3) -> dict:
        """
        Aggregates activity stats from InfluxDB for the last N days.
        """
        try:
            query_api = InfluxClientWrapper.get_query_api()
            bucket = settings.INFLUXDB_BUCKET
            org = settings.INFLUXDB_ORG
            
            # Flux Query: Aggregate duration by category
            # Ensure your LogService writes 'category' as a tag.
            flux_query = f'''
            from(bucket: "{bucket}")
              |> range(start: -{days}d)
              |> filter(fn: (r) => r["_measurement"] == "user_activity_v2")
              |> filter(fn: (r) => r["user_id"] == "{user_id}")
              |> filter(fn: (r) => r["_field"] == "duration_min")
              |> group(columns: ["category"])
              |> sum()
            '''
            
            # Execute Sync Query in Thread Pool to avoid blocking Event Loop
            import asyncio
            loop = asyncio.get_running_loop()
            
            # Use partial to pass arguments to the sync function
            from functools import partial
            tables = await loop.run_in_executor(
                None, 
                partial(query_api.query, org=org, query=flux_query)
            )
            
            study_min = 0
            play_min = 0
            
            for table in tables:
                for record in table.records:
                    cat = record.values.get("category")
                    val = record.get_value() or 0
                    if cat == "STUDY":
                        study_min += val
                    elif cat == "PLAY":
                        play_min += val
            
            total = study_min + play_min
            ratio = (play_min / total * 100.0) if total > 0 else 0.0
            
            # Get Recent Violations (Raw Data)
            # Limit to last 3 events of category PLAY
            viol_query = f'''
            from(bucket: "{bucket}")
              |> range(start: -{days}d)
              |> filter(fn: (r) => r["_measurement"] == "user_activity_v2")
              |> filter(fn: (r) => r["user_id"] == "{user_id}")
              |> filter(fn: (r) => r["category"] == "PLAY")
              |> filter(fn: (r) => r["_field"] == "action_detail")
              |> sort(columns: ["_time"], desc: true)
              |> limit(n: 3)
            '''
            viol_tables = await loop.run_in_executor(
                None,
                partial(query_api.query, org=org, query=viol_query)
            )
            violations = []
            for table in viol_tables:
                for record in table.records:
                    val = record.get_value()
                    # format time
                    t_str = record.get_time().strftime("%Y-%m-%d %H:%M")
                    violations.append(f"{val} ({t_str})")

            return {
                "study_count": study_min, # In minutes now
                "play_count": play_min,   # In minutes now
                "ratio": ratio,
                "violations": violations
            }
            
        except Exception as e:
            print(f"[StatisticService] Influx Query Error: {e}")
            return {
                "study_count": 0, "play_count": 0, "ratio": 0.0, "violations": []
            }

    async def get_daily_timeline(self, user_id: str) -> list[str]:
        """
        Retrieves a chronological list of activities for Today.
        Used for Daily Wrapped.
        """
        try:
            query_api = InfluxClientWrapper.get_query_api()
            bucket = settings.INFLUXDB_BUCKET
            org = settings.INFLUXDB_ORG
            
            # Flux Query: Get all user activity for today
            flux_query = f'''
            from(bucket: "{bucket}")
              |> range(start: -24h)
              |> filter(fn: (r) => r["_measurement"] == "user_activity_v2")
              |> filter(fn: (r) => r["user_id"] == "{user_id}")
              |> filter(fn: (r) => r["_field"] == "action_detail")
              |> sort(columns: ["_time"], desc: false)
            '''
            
            import asyncio
            loop = asyncio.get_running_loop()
            from functools import partial
            
            tables = await loop.run_in_executor(
                None, 
                partial(query_api.query, org=org, query=flux_query)
            )
            
            timeline = []
            for table in tables:
                for record in table.records:
                    t_str = record.get_time().strftime("%H:%M")
                    val = record.get_value()
                    cat = record.values.get("category", "UNKNOWN")
                    # Ignore QUIZ details in timeline if needed, or include them
                    timeline.append(f"[{t_str}] {val} ({cat})")
            
            return timeline
        except Exception as e:
            print(f"[StatisticService] Timeline Error: {e}")
            return []

    async def get_daily_quiz_logs(self, user_id: str) -> list[dict]:
        """
        Retrieves Quiz Logs for Today (Score + Wrong Answers).
        """
        try:
            query_api = InfluxClientWrapper.get_query_api()
            bucket = settings.INFLUXDB_BUCKET
            org = settings.INFLUXDB_ORG
            
            # Fetch Score & Wrong Answers
            # We need to query multiple fields
            flux_query = f'''
            from(bucket: "{bucket}")
              |> range(start: -24h)
              |> filter(fn: (r) => r["_measurement"] == "user_activity_v2")
              |> filter(fn: (r) => r["user_id"] == "{user_id}")
              |> filter(fn: (r) => r["type"] == "QUIZ")
              |> filter(fn: (r) => r["_field"] == "score" or r["_field"] == "action_detail" or r["_field"] == "wrong_answers")
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            import asyncio
            loop = asyncio.get_running_loop()
            from functools import partial
            
            tables = await loop.run_in_executor(
                None,
                partial(query_api.query, org=org, query=flux_query)
            )
            
            logs = []
            for table in tables:
                for record in table.records:
                    logs.append({
                        "topic": record.values.get("action_detail", "Unknown Quiz"),
                        "score": record.values.get("score", 0),
                        "wrong_answers": record.values.get("wrong_answers", "[]")
                    })
            return logs
        except Exception as e:
            print(f"[StatisticService] Quiz Log Error: {e}")
            return []

statistic_service = StatisticService()
