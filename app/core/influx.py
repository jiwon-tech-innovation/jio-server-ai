from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from app.core.config import get_settings

settings = get_settings()

class InfluxClientWrapper:
    _client: InfluxDBClient = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            cls._client = InfluxDBClient(
                url=settings.INFLUXDB_URL,
                token=settings.INFLUXDB_TOKEN,
                org=settings.INFLUXDB_ORG,
                timeout=500  # 0.5s timeout for fast fail-over
            )
        return cls._client

    @classmethod
    def get_write_api(cls):
        client = cls.get_client()
        return client.write_api(write_options=SYNCHRONOUS)

    @classmethod
    def get_query_api(cls):
        client = cls.get_client()
        return client.query_api()

# Global accessor
def get_influx_client():
    return InfluxClientWrapper.get_client()
