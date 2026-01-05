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
              |> filter(fn: (r) => r["_measurement"] == "user_activity")
              |> filter(fn: (r) => r["user_id"] == "{user_id}")
              |> filter(fn: (r) => r["_field"] == "duration_min")
              |> group(columns: ["category"])
              |> sum()
            '''
            
            # Execute Sync Query (Blocking, but okay for low load)
            tables = query_api.query(org=org, query=flux_query)
            
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
              |> filter(fn: (r) => r["_measurement"] == "user_activity")
              |> filter(fn: (r) => r["user_id"] == "{user_id}")
              |> filter(fn: (r) => r["category"] == "PLAY")
              |> filter(fn: (r) => r["_field"] == "action_detail")
              |> sort(columns: ["_time"], desc: true)
              |> limit(n: 3)
            '''
            viol_tables = query_api.query(org=org, query=viol_query)
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
            
            # Simple query: Get all points for today
            flux_query = f'''
            from(bucket: "{bucket}")
              |> range(start: -24h)
              |> filter(fn: (r) => r["_measurement"] == "user_activity")
              |> filter(fn: (r) => r["user_id"] == "{user_id}")
              |> filter(fn: (r) => r["_field"] == "action_detail")
              |> sort(columns: ["_time"], desc: false)
            '''
            
            tables = query_api.query(org=org, query=flux_query)
            timeline = []
            for table in tables:
                for record in table.records:
                    # Time + Action + Category (from tag)
                    t_str = record.get_time().strftime("%H:%M")
                    val = record.get_value()
                    cat = record.values.get("category", "UNKNOWN")
                    timeline.append(f"[{t_str}] {val} ({cat})")
            
            return timeline
        except Exception as e:
            print(f"[StatisticService] Timeline Error: {e}")
            return []

statistic_service = StatisticService()
