from datetime import datetime
from influxdb_client import Point
from app.core.config import get_settings
from app.core.influx import InfluxClientWrapper

settings = get_settings()

class LogService:
    def __init__(self):
        self.bucket = settings.INFLUXDB_BUCKET
        self.org = settings.INFLUXDB_ORG

    def log_activity(self, user_id: str, category: str, action_detail: str, duration_min: int = 1):
        """
        Writes an activity log to InfluxDB.
        """
        try:
            write_api = InfluxClientWrapper.get_write_api()
            
            # Measurement: user_activity
            # Tags: user_id, category
            # Fields: duration_min, action_detail (as string field if needed, but usually fields are numeric. 
            # InfluxDB supports string fields, but better to use tags for low cardinality. 
            # action_detail might be high cardinality, so let's keep it as field or tag carefully.
            # Here we act as a 'Fact', so maybe field is safer.)
            
            point = Point("user_activity") \
                .tag("user_id", user_id) \
                .tag("category", category) \
                .field("duration_min", duration_min) \
                .field("action_detail", action_detail) \
                .time(datetime.utcnow())
                
            write_api.write(bucket=self.bucket, org=self.org, record=point)
            print(f"[LogService] InfluxDB Write Success: {category} - {action_detail}")
            
        except Exception as e:
            print(f"[LogService] InfluxDB Write Failed: {e}")

log_service = LogService()
